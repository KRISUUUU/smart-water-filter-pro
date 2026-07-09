# Intelligence Engines & State Machines

The Smart Water Filter PRO integration contains three independent logic engines that analyze physical data to generate predictive maintenance alerts, clogging indicators, and safety alarms.

---

## 1. Predictor Engine: Volumetric & Temporal Decay

The Predictor Engine calculates how many days are left until the filter cartridge needs replacement and provides a confidence rating of this prediction.

### Mathematical Models

#### Estimated Days Remaining ($Days_{remaining}$)
The predicted remaining lifespan is a function of both physical volume decay and maximum calendar age limits. It represents the *minimum* of these two constraints:

\[ Days_{remaining} = \min(Days_{volume}, Days_{age}) \]

Where:
- **Calendar Decay ($Days_{age}$)**: Tracks absolute elapsed time against the physical cartridge manufacturer expiration threshold (typically $MaxAge_{days} = 365.0$).
  \[ Days_{age} = \max(0.0, MaxAge_{days} - Age_{days}) \]

- **Volumetric Decay ($Days_{volume}$)**: Computes when the remaining filter capacity will be exhausted based on the consumption velocity, calculated via Exponential Moving Average ($EMA_{daily\_velocity}$).
  \[ Days_{volume} = \lceil \frac{Volume_{capacity} - Volume_{consumed}}{EMA_{daily\_velocity}} \rceil \]

- **Edge Case (Near-Zero Usage)**: To prevent division by zero or inflated forecasts during vacations, if $EMA_{daily\_velocity} \le 0.5\text{ L/day}$, then:
  \[ Days_{remaining} = Days_{age} \]

#### Prediction Confidence Rating ($Confidence$)
The confidence score (expressed from 0% to 100%) represents the statistical stability of the forecast. It is derived using the history length and standard deviation of daily usage.

Let $N$ be the number of recorded days in the daily consumption history (capped at 30 days).
1. **Base Sample Score ($Score_{base}$)**: Accumulates $5\%$ confidence per daily sample, capped at $85\%$.
   \[ Score_{base} = \min(85, N \times 5) \]
   If $N < 3$, $Confidence = Score_{base}$.

2. **Usage Volatility Adjustment**:
   Let $x_i$ represent the daily water usage (in Liters) for day $i \in \{1..N\}$, with mean $\mu$ and standard deviation $\sigma$.
   The **Coefficient of Variation ($CV$)** represents the normalized dispersion of usage:
   \[ CV = \frac{\sigma}{\mu} \]
   If $\mu > 1.0$, a high $CV$ indicates volatile usage patterns. A volatility penalty ($P$) is applied:
   \[ P = \min(30.0, CV \times 30.0) \]

3. **Stability Bonus ($B$)**:
   If the user has established a long history ($N \ge 14$) with high consumption stability ($CV < 0.20$), a stability bonus is granted:
   \[ B = 15.0 \]

4. **Final Confidence Formula**:
   \[ Confidence = \max(0.0, \min(100.0, \text{round}(Score_{base} - P + B))) \]

---

## 2. Hydrodynamic Degradation Engine (Filter Engine)

Unlike volumetric calculations, physical membrane clogging is non-linear and is derived by tracking flow resistance during active usage.

### Flow Rate Degradation ($FlowDegradation$)
The engine records peak flow rate baselines in two phases:
1. **Baseline Peak ($Peak_{baseline}$)**: The highest flow rate ($L/min$) recorded during the first $100\text{ L}$ of the filter cartridge life.
2. **Current Peak ($Peak_{recent}$)**: The highest flow rate ($L/min$) recorded in the usage history *after* the initial $100\text{ L}$ threshold.

The degradation percentage represents the drop in max achievable flow rate due to physical sediment clogging:

\[ FlowDegradation = \begin{cases} 
      0.0\% & \text{if } Peak_{baseline} \le 0.5 \text{ or } Peak_{recent} \ge Peak_{baseline} \\
      \frac{Peak_{baseline} - Peak_{recent}}{Peak_{baseline}} \times 100\% & \text{otherwise}
   \end{cases} \]

### Clogging Status
The integration maps $FlowDegradation$ to the binary clogging warning sensor:
- **`normal`**: $FlowDegradation \le 20.0\%$
- **`warning`**: $20.0\% < FlowDegradation \le 35.0\%$ (Clogging status is `OFF`, but health score decreases)
- **`restricted`**: $FlowDegradation > 35.0\%$ (Clogging status binary sensor switches `ON`)

### Hybrid Health Score ($Health$)
To prevent early warnings from volume alone when flow is healthy, or membrane rupture warnings when volume is high, the overall health score is a weighted hybrid:

\[ Health_{raw} = (VolumeHealth \times 0.4) + (TimeHealth \times 0.2) + (FlowHealth \times 0.4) \]

Where:
- $VolumeHealth = \frac{RemainingLiters}{Capacity} \times 100\%$
- $TimeHealth = \max(0.0, \frac{MaxAge - Age}{MaxAge} \times 100\%)$
- $FlowHealth = \max(0.0, 100.0 - FlowDegradation)$

**Critical Overrides**:
- If flow health drops due to heavy clogging ($FlowHealth < 30.0$), the final health is capped: $Health = \min(Health_{raw}, 50.0)$.
- If the filter is expired or fully consumed ($VolumeHealth == 0.0$ or $TimeHealth == 0.0$), health is capped: $Health = \min(Health_{raw}, 10.0)$.

---

## 3. Leak Engine: Finite-State Machine Specification

The Leak Engine executes continuous volume and duration checks over an active flow stream to differentiate between standard usage and plumbing failures.

### State Transition Diagram
```
    +-------------------------------------------------------------+
    |                                                             |
    v                                                             | Clear Alarm
+--------+   Flow > Threshold for Duration    +---------------+   |
| NORMAL | ---------------------------------> | ALARM ACTIVE  | --+
+--------+                                    +---------------+
    |                                                 |
    +------- Flow > Instantaneous Critical Limit -----+
```

### State Definitions & Trigger Thresholds

The leak engine operates under four modes depending on household activity:

#### A. Standard Mode (Default)
Optimized for standard domestic profiles.
- **NORMAL**: Volumetric flow rate is $0.0\text{ L/min}$ or intermittent. No timers active.
- **MICRO**: Continuous flow $> 0.05\text{ L/min}$ for $\ge 30\text{ consecutive minutes}$. Indicates slow fitting leak or dripping faucet.
- **HIGH**: Continuous flow $> 1.00\text{ L/min}$ for $\ge 10\text{ consecutive minutes}$. Indicates faucet left open or line rupture.
- **CRITICAL**: Instantaneous flow $> 5.00\text{ L/min}$ (no duration threshold). Indicates pipe burst.

#### B. Away Mode
Aggressive thresholds for when the house is empty.
- **MICRO**: Continuous flow $> 0.01\text{ L/min}$ for $\ge 2\text{ consecutive minutes}$.
- **HIGH**: Continuous flow $> 0.20\text{ L/min}$ for $\ge 1\text{ consecutive minute}$.
- **CRITICAL**: Instantaneous flow $> 1.00\text{ L/min}$.

#### C. Kitchen/RO Mode
Loose bounds to prevent false alarms during slow Reverse Osmosis (RO) filtration membrane flushes.
- **MICRO**: Continuous flow $> 0.02\text{ L/min}$ for $\ge 120\text{ consecutive minutes}$.
- **HIGH**: Continuous flow $> 0.50\text{ L/min}$ for $\ge 20\text{ consecutive minutes}$.
- **CRITICAL**: Instantaneous flow $> 3.00\text{ L/min}$.

#### D. Disabled Mode
State machine tracking bypassed. Alarms cannot be triggered. Active alarms remain latched until cleared.

---

## 4. Alarm Latching Behavior
Once any leak state transitions to an active alarm (`micro`, `high`, or `critical`), the state is **latched**. Even if flow stops completely, the alarm entity remains `ON` and the severity is locked. The alarm can only be reset by calling the `button.reset_filter` or a custom `clear_alarm` service.
