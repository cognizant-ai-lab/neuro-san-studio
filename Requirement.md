Requirement R-CC-001 — Adaptive Cruise Control (ACC) Basic Speed Hold
Description:  
The vehicle shall maintain a driver‑set target speed on straight roads when no slower lead vehicle is detected within the lane.

Rationale:  
Provide basic longitudinal automation to reduce driver workload and demonstrate closed‑loop control modeling and verification.

Priority: High

Type: Functional

Inputs:

Vehicle speed 
𝑣
𝑣
𝑒
ℎ
 (m/s)

Driver target speed 
𝑣
𝑠
𝑒
𝑡
 (m/s)

Lead vehicle detection flag lead_detected (boolean)

Lead vehicle speed 
𝑣
𝑙
𝑒
𝑎
𝑑
 (m/s) — only valid if lead_detected == true

Outputs:

Throttle command (0–100%)

Brake command (0–100%)

System mode: ACTIVE / INACTIVE

Functional Requirements (concise):

When lead_detected == false and system ENABLED, controller shall drive throttle/brake to maintain 
𝑣
𝑣
𝑒
ℎ
≈
𝑣
𝑠
𝑒
𝑡
 within ±1.0 m/s steady‑state error.

If 
𝑣
𝑣
𝑒
ℎ
>
𝑣
𝑠
𝑒
𝑡
+
1.0
 m/s, apply braking command to reduce speed.

If 
𝑣
𝑣
𝑒
ℎ
<
𝑣
𝑠
𝑒
𝑡
−
1.0
 m/s, apply throttle command to increase speed.

If lead_detected == true, ACC shall hand off to distance‑keeping mode (out of scope for this basic requirement).

Nonfunctional Constraints:

Control loop sample time: 50 ms.

Controller must be implementable with standard Simulink blocks and run in fixed‑step simulation.

No use of proprietary customer data.

Acceptance Criteria / Verification Tests:

Steady‑state test: With 
𝑣
𝑠
𝑒
𝑡
=
25
 m/s and no lead vehicle, after 30 s simulation, 
∣
𝑣
𝑣
𝑒
ℎ
−
𝑣
𝑠
𝑒
𝑡
∣
≤
1.0
 m/s.

Step response test: From initial 
𝑣
𝑣
𝑒
ℎ
=
20
 m/s to 
𝑣
𝑠
𝑒
𝑡
=
25
 m/s, rise time 
𝑡
𝑟
<
8
 s and overshoot < 10%.

Safety check: Throttle and brake commands never exceed 100% and are never commanded simultaneously (mutual exclusion).

Timing: All control outputs updated at 50 ms intervals.

Modeling Notes (for Simulink Creator Agent):

Implement a PID or PI speed controller block with anti‑windup.

Plant: simple longitudinal vehicle model (mass, drag, rolling resistance) or use a first‑order approximation.

Inputs/outputs exposed as top‑level Inport/Outport for test harness.

Provide parameter set file (params.mat) with vehicle mass, drag coefficient, sample time.

Verification Artifacts (for Verification Agent):

Simulink Test harness with the three test scenarios above.

Plots: speed vs time, throttle/brake vs time, error vs time.

Pass/fail logic for acceptance criteria.