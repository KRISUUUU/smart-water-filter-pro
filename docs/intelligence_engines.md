# Intelligence Engines & State Machines

The Smart Water Filter PRO integration contains three independent logic engines that analyze physical data to generate predictive maintenance alerts, clogging indicators, and safety alarms. In version 5.0.0, prediction models and clogging status run independently per filter stage, while the leak engine remains a unified safety guardrail for the main water line.

---

## 1. Predictor Engine: Volumetric & Temporal Decay

The Predictor Engine calculates how many days are left until a specific filter stage cartridge needs replacement and provides a confidence rating of this prediction.

### Mathematical Models (Executed Per-Stage)

#### Estimated Days Remaining ($Days_{remaining, s}$ for Stage $s$)
The predicted remaining lifespan is a function of both physical volume decay and maximum calendar age limits of the specific stage. It represents the *minimum* of these two constraints:

\[ Days_{remaining, s} = \min(Days_{volume, s}, Days_{age, s}) \]

Where:
- **Calendar Decay ($Days_{age, s}$)**: Tracks absolute elapsed time against the physical expiration threshold for the specific stage $s$ ($MaxAge_{days, s}$).
  \[ Days_{age, s} = \max(0.0, MaxAge_{days, s} - Age_{days, s}) \]

- **Volumetric Decay ($Days_{volume, s}$)**: Computes when the remaining filter capacity will be exhausted based on the consumption velocity, calculated via the global Exponential Moving Average ($EMA_{daily\_velocity}$).
  \[ Days_{volume, s} = \lceil \frac{Volume_{capacity, s} - Volume_{consumed, s}}{EMA_{daily\_velocity}} \rceil \]

- **Edge Case (Near-Zero Usage)**: To prevent division by zero or inflated forecasts during vacations, if $EMA_{daily\_velocity} \le 0.5\text{ L/day}$, then:
  \[ Days_{remaining, s} = Days_{age, s} \]

#### Prediction Confidence Rating ($Confidence$)
The confidence score (expressed from 0% to 100%) represents the statistical stability of the forecast. It is derived using the global history length and standard deviation of daily usage, meaning it represents the predictability of household consumption rather than stage details.

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

## 2. Hydrodynamic Degradation Engine (Executed Per-Stage)

Unlike volumetric calculations, physical membrane clogging is non-linear and is derived by tracking flow resistance during active usage.

### Flow Rate Degradation ($FlowDegradation_s$ for Stage $s$)
Each filter stage records peak flow rate baselines in two phases:
1. **Baseline Peak ($Peak_{baseline, s}$)**: The highest flow rate ($L/min$) recorded during the first $100\text{ L}$ of stage usage.
2. **Current Peak ($Peak_{recent, s}$)**: The highest flow rate ($L/min$) recorded in the usage history *after* the initial $100\text{ L}$ threshold.

The degradation percentage represents the drop in max achievable flow rate due to physical sediment clogging of the specific stage membrane:

\[ FlowDegradation_s = \begin{cases} 
      0.0\% & \text{if } Peak_{baseline, s} \le 0.5 \text{ or } Peak_{recent, s} \ge Peak_{baseline, s} \\
      \frac{Peak_{baseline, s} - Peak_{recent, s}}{Peak_{baseline, s}} \times 100\% & \text{otherwise}
   \end{cases} \]

### Clogging Status
The integration maps $FlowDegradation_s$ to the clogging status of stage $s$:
- **`normal`**: $FlowDegradation_s \le 20.0\%$
- **`warning`**: $20.0\% < FlowDegradation_s \le 35.0\%$ (Clogging status is `OFF`, but health score decreases)
- **`restricted`**: $FlowDegradation_s > 35.0\%$ (Clogging status alert switches `ON`)

### Hybrid Health Score ($Health_s$ for Stage $s$)
To prevent early warnings from volume alone when flow is healthy, or membrane rupture warnings when volume is high, the overall health score of stage $s$ is a weighted hybrid:

\[ Health_{raw, s} = (VolumeHealth_s \times 0.4) + (TimeHealth_s \times 0.2) + (FlowHealth_s \times 0.4) \]

Where:
- $VolumeHealth_s = \frac{RemainingLiters_s}{Capacity_s} \times 100\%$
- $TimeHealth_s = \max(0.0, \frac{MaxAge_s - Age_s}{MaxAge_s} \times 100\%)$
- $FlowHealth_s = \max(0.0, 100.0 - FlowDegradation_s)$

**Critical Overrides**:
- If flow health drops due to heavy clogging ($FlowHealth_s < 30.0$), the stage health is capped: $Health_s = \min(Health_{raw, s}, 50.0)$.
- If the filter is expired or fully consumed ($VolumeHealth_s == 0.0$ or $TimeHealth_s == 0.0$), health is capped: $Health_s = \min(Health_{raw, s}, 10.0)$.

---

## 3. Leak Engine: Finite-State Machine Specification

The Leak Engine executes continuous volume and duration checks over an active flow stream to differentiate between standard usage and plumbing failures. Unlike the filter engine, it operates globally at the main water line hub.

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
Once any leak state transitions to an active alarm (`micro`, `high`, or `critical`), the state is **latched**. Even if flow stops completely, the alarm entity remains `ON` and the severity is locked. The alarm can only be reset by calling the `clear_alarm` service action.
