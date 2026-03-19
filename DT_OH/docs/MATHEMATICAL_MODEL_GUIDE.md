# Retinal Hemodynamics Model - Mathematical Computation Guide

## Overview

This document explains the mathematical model for retinal blood flow simulation (Shimpatica lumped parameter model). The model simulates hemodynamics in the retinal circulation using a system of ordinary differential equations (ODEs).

## Model Architecture

The model represents the retinal circulation as an **electrical circuit analog** with:
- **Pressures** (P1, P2, P4, P5) at 4 nodes representing different vascular segments
- **Resistances** (R) representing vessel resistance to flow
- **Capacitances** (C1, C2, C4, C5) representing vessel compliance
- **Flow rates** (Q) representing blood flow between nodes

### Vascular Network Structure

```
Input → [R_in + R_1a] → P1 → [R_1b + R_1c + R_1d + R_2a] → P2 
         ↓ C1                    ↓ C2
         
P2 → [R_2b + R_3a + R_3b + R_4a] → P4 → [R_4b + R_5a + R_5b + R_5c] → P5
         ↓ C4                    ↓ C5
         
P5 → [R_5d + R_out] → P_out (14.00 mmHg)
```

## Mathematical Components

### 1. Model Constants

#### Fixed Resistances (mm Hg·s/mL)
These are constant resistances in the circuit:
- `R_in = 2.25e4` - Input resistance
- `R_1a = 4.30e3`, `R_1b = 4.30e3` - Central Retinal Artery (CRA) segments
- `R_2a = 6.00e3`, `R_2b = 6.00e3` - Intermediate segments
- `R_3a = 5.68e3`, `R_3b = 5.68e3` - Pre-capillary segments
- `R_5c = 1.35e3`, `R_5d = 1.35e3` - Central Retinal Vein (CRV) segments
- `R_out = 5.74e3` - Output resistance
- `P_out = 14.00` - Output pressure (mmHg)

#### Capacitances (mL/mmHg)
Vessel compliance values:
- `C1 = 7.22e-7` - Node 1 capacitance
- `C2 = 7.53e-7` - Node 2 capacitance
- `C4 = 1.67e-5` - Node 4 capacitance
- `C5 = 1.07e-5` - Node 5 capacitance

#### Material Properties

**Central Retinal Artery (CRA):**
- Viscosity: `mu_CRA = 3.0 cP` → converted to `2.25e-5 mmHg·s`
- Young's Modulus: `E_CRA = 0.3 MPa` → converted to `2.25e6 mmHg`
- Reference diameter: `d_CRA_ref = 175e-4 cm` (radius = 87.5e-4 cm)
- Wall thickness: `h_CRA = 39.7239e-4 cm`
- Segment lengths: `L_1c = 0.2e-1 cm`, `L_1d = 1e-1 cm`

**Central Retinal Vein (CRV):**
- Viscosity: `mu_CRV = 3.24 cP` → converted to `2.43e-5 mmHg·s`
- Young's Modulus: `E_CRV = 0.6 MPa` → converted to `4.5e6 mmHg`
- Reference diameter: `d_CRV_ref = 238e-4 cm` (radius = 119e-4 cm)
- Wall thickness: `h_CRV = 10.7e-4 cm`
- Segment lengths: `L_5a = 1e-1 cm`, `L_5b = 0.2e-1 cm`

**Venules:**
- Viscosity: `mu_VEN = 3.24 cP` → converted to `2.43e-5 mmHg·s`
- Young's Modulus: `E_VEN = 0.066 MPa` → converted to `4.95e5 mmHg`
- Reference diameter: `d_VEN_ref = 0.015476685724901 cm` (radius = 0.007738 cm)
- Wall thickness: `h_VEN = d_VEN_ref / 20`
- Equivalent length: `L_VEN = 0.413520 cm` (split into `L_4a = L_4b = L_VEN/2`)

**Common:**
- Poisson's ratio: `v = 0.49` (wall material property)

#### Derived Parameters

For each vessel type, the following are calculated:

1. **Reference cross-sectional area:**
   ```
   A_ref = π × r_ref²
   ```

2. **Geometric factor K_l:**
   ```
   K_l = 12 × A_ref / (π × h²)
   ```

3. **Pressure factor K_p:**
   ```
   K_p = (1/12) × (E × h³ / (1 - v²)) × (π / A_ref)^(3/2)
   ```

4. **Base conductance k0:**
   ```
   k0 = A_ref² / (8 × π × μ × L)
   ```
   Where μ is viscosity and L is segment length.

### 2. Input Pressure Waveform: `Pin_Waveform(time, c)`

This function generates the time-varying input pressure based on:
- `c[0]` = Systolic Blood Pressure (SBP)
- `c[1]` = Diastolic Blood Pressure (DBP)
- `c[2]` = Intraocular Pressure (IOP)
- `c[3]` = Heart Rate (HR) - **NOTE: Currently hardcoded to 80 bpm**

The waveform is piecewise-defined over one cardiac cycle (Thr = 60/HR):

1. **Early systole (0 ≤ t ≤ 0.082×Thr):**
   ```
   Pin = 0.65×SBP - 0.475×DBP×sin(2π×t/(4×0.082×Thr) + 2π×0.082×Thr/(0.328×Thr))
   ```

2. **Systolic upstroke (0.082×Thr < t ≤ 0.112×Thr):**
   ```
   Pin = 0.65×SBP + 0.9×sin(2π×t/(0.03×Thr) - 2π×0.082×Thr/(0.03×Thr))
   ```

3. **Systolic plateau (0.112×Thr < t ≤ 0.398×Thr):**
   ```
   Pin = 0.65×SBP + 0.118×SBP×sin(2π×t/(0.572×Thr) - 2π×0.112×Thr/(0.572×Thr))
   ```

4. **Early diastole (0.398×Thr < t ≤ 0.432×Thr):**
   ```
   Pin = -(0.13×SBP×t/(0.034×Thr)) + 0.65×SBP + (0.13×SBP×0.398×Thr/(0.034×Thr))
   ```

5. **Dicrotic notch (0.432×Thr < t ≤ 0.482×Thr):**
   ```
   Pin = 0.52×SBP - 0.8×sin(2π×t/(0.05×Thr) + 2π×0.332×Thr/(0.05×Thr))
   ```

6. **Diastolic decay (t > 0.482×Thr):**
   ```
   Pin = 0.52×SBP + (0.52×SBP - 0.5×DBP)×sin(2π×t/(2.072×Thr) + 2π×0.554×Thr/(2.072×Thr))
   ```

### 3. Variable Resistances

Resistances change based on **transmural pressure** (pressure difference across vessel wall):
```
ΔP = P_vessel - IOP
```

#### CRA Resistances (R_1c, R_1d)
Always use the same formula (vessels don't collapse):
```
R = (1/k0) × (1 + ΔP/(K_p × K_l))^(-4)
```

#### Venule Resistances (R_4a, R_4b)
**If ΔP ≥ 0 (vessel distended):**
```
R = (1/k0) × (1 + ΔP/(K_p × K_l))^(-4)
```

**If ΔP < 0 (vessel collapsed):**
```
R = (1/k0) × (1 - ΔP/K_p)^(4/3)
```

#### CRV Resistances (R_5a, R_5b)
Same piecewise formula as venules:
- If ΔP ≥ 0: `R = (1/k0) × (1 + ΔP/(K_p × K_l))^(-4)`
- If ΔP < 0: `R = (1/k0) × (1 - ΔP/K_p)^(4/3)`

### 4. ODE System: `f(time, P, c)`

The model solves a system of 4 ODEs representing pressure changes at each node:

**State variables:** `P = [P1, P2, P4, P5]` (pressures at nodes 1, 2, 4, 5)

**ODE Equations:**

1. **dP1/dt = F1:**
   ```
   F1 = ((Pin - P1)/(R_in + R_1a) - (P1 - P2)/(R_1b + R_1c + R_1d + R_2a)) / C1
   ```
   Rate of change at node 1 = (inflow - outflow) / capacitance

2. **dP2/dt = F2:**
   ```
   F2 = ((P1 - P2)/(R_1b + R_1c + R_1d + R_2a) - (P2 - P4)/(R_2b + R_3a + R_3b + R_4a)) / C2
   ```

3. **dP4/dt = F3:**
   ```
   F3 = ((P2 - P4)/(R_2b + R_3a + R_3b + R_4a) - (P4 - P5)/(R_4b + R_5a + R_5b + R_5c)) / C4
   ```

4. **dP5/dt = F4:**
   ```
   F4 = ((P4 - P5)/(R_4b + R_5a + R_5b + R_5c) - (P5 - P_out)/(R_5d + R_out)) / C5
   ```

**Physical Interpretation:**
- Each equation represents conservation of mass at a node
- Flow = Pressure difference / Resistance (Ohm's law analog)
- Rate of pressure change = Net flow / Capacitance

### 5. ODE Solver

The system is solved using `scipy.integrate.solve_ivp`:
- **Method:** BDF (Backward Differentiation Formula) - suitable for stiff systems
- **Tolerance:** `atol=1e-8`, `rtol=1e-8` (very high precision)
- **Time span:** `[0, Tfin]` where `Tfin = 10 × (60/HR)` (10 cardiac cycles)
- **Initial conditions:** `P0 = [P1, P2, P4, P5]` from lookup table based on IOP

### 6. Post-Processing: `PostProcessing(t, P, c)`

After solving the ODE, this function computes:

#### A. Delta Pressures (vectorized)
```
deltaP1c = P[0] - c[2]  # Array: P1(t) - IOP for all time points
deltaP1d = P[0] - c[2]
deltaP4a = P[2] - c[2]  # P4(t) - IOP
deltaP4b = P[2] - c[2]
deltaP5a = P[3] - c[2]  # P5(t) - IOP
deltaP5b = P[3] - c[2]
```

#### B. Resistances (vectorized)
For each time point, compute resistances using the same formulas as in `f()`:
- `R_1c`, `R_1d`: CRA formula
- `R_4a`, `R_4b`: Venule piecewise formula
- `R_5a`, `R_5b`: CRV piecewise formula

**⚠️ KNOWN BUG:** In `PostProcessing()`, `R_4b` incorrectly uses `k0_VEN_4a` instead of `k0_VEN_4b`. This is present in the original code and should be fixed for accuracy.

#### C. Flow Rates (vectorized)
```
Qin  = (Pin(t) - P1(t)) / (R_in + R_1a)
Q12  = (P1(t) - P2(t)) / (R_1b + R_1c(t) + R_1d(t) + R_2a)
Q24  = (P2(t) - P4(t)) / (R_2b + R_3a + R_3b + R_4a(t))
Q45  = (P4(t) - P5(t)) / (R_4b(t) + R_5a(t) + R_5b(t) + R_5c)
Qout = (P5(t) - P_out) / (R_5d + R_out)
```

#### D. Derivatives (for RNN analysis)
```
F1 = (Qin - Q12) / C1
F2 = (Q12 - Q24) / C2
F3 = (Q24 - Q45) / C4
F4 = (Q45 - Qout) / C5
```

### 7. Output Extraction: `_shimpatica_func()`

From the last cardiac cycle (9th to 10th cycle), extract:

#### Pressure Statistics
For each pressure (P1, P2, P4, P5):
- **Systolic:** Maximum value
- **Diastolic:** Minimum value
- **Mean:** Time-averaged (trapezoidal integration)

#### Flow Statistics
For each flow (Q12, Q24, Q45):
- **Systolic:** Maximum value
- **Diastolic:** Minimum value
- **Mean:** Time-averaged

#### Resistance Statistics
For each resistance (R_1c, R_1d, R_4a, R_4b, R_5a, R_5b):
- **Systolic:** Minimum value (lower resistance = higher flow)
- **Diastolic:** Maximum value
- **Mean:** Time-averaged

#### Final Outputs
1. **P1mean, P2mean, P4mean, P5mean:** Mean pressures at each node
2. **Qmean:** Average of Q12mean, Q24mean, Q45mean
3. **R1:** Trapezoidal integration of [R1cmean, R1dmean, R_1a, R_1b]
4. **R4:** Sum of R4amean + R4bmean
5. **R5:** Trapezoidal integration of [R5amean, R5bmean, R_5c, R_5d]

## Known Issues and Recommendations

### 1. ⚠️ CRITICAL: PostProcessing R_4b Bug

**Location:** `PostProcessing()` function, line ~297-298

**Issue:** `R_4b` calculation uses `k0_VEN_4a` instead of `k0_VEN_4b`

**Current (incorrect):**
```python
R_4b = [(1/k0_VEN_4a) * (1 + dp4b/(K_p_VEN*K_l_VEN))**(-4) if dp4b >= 0 else
        (1/k0_VEN_4a) * (1 - dp4b/(K_p_VEN))**(4/3) for dp4b in deltaP4b]
```

**Should be:**
```python
R_4b = [(1/k0_VEN_4b) * (1 + dp4b/(K_p_VEN*K_l_VEN))**(-4) if dp4b >= 0 else
        (1/k0_VEN_4b) * (1 - dp4b/(K_p_VEN))**(4/3) for dp4b in deltaP4b]
```

**Impact:** This affects R4 calculations and potentially flow rates Q24 and Q45.

**Note:** The `f()` function correctly uses `k0_VEN_4b` for R_4b during ODE solving, so the ODE solution is correct. Only the post-processing analysis is affected.

### 2. Heart Rate Hardcoding

**Location:** `Pin_Waveform()` function

**Issue:** HR is hardcoded to 80 bpm instead of using `c[3]`

**Current:**
```python
HR = 80  # HR = c[3]  (commented out)
```

**Recommendation:** Use actual HR from input:
```python
HR = c[3]  # Use actual heart rate from input
```

**Impact:** All patients are simulated with 80 bpm regardless of actual HR, affecting cardiac cycle timing and waveform shape.

### 3. Global Variable State

**Issue:** Global lists (T, Pin, R1c, R1d, etc.) are appended to during ODE solving but never cleared between patients.

**Impact:** In parallel processing, this could cause cross-contamination. However, since each process has its own memory space, this is not an issue in the current implementation.

**Recommendation:** For safety, clear globals at the start of each simulation or use instance variables.

## Code Verification Checklist

✅ **Constants:** All resistance, capacitance, and material property values match  
✅ **Pin_Waveform:** All 6 piecewise segments match exactly  
✅ **f() function:** ODE equations, resistance calculations, and variable updates match  
✅ **PostProcessing:** Delta pressure calculations, resistance formulas, flow calculations match  
✅ **Output extraction:** Statistics calculations (min/max/mean) match  
⚠️ **PostProcessing R_4b:** Uses wrong k0 constant (matches original bug)  
⚠️ **Pin_Waveform HR:** Hardcoded to 80 (matches original)

## Physical Model Interpretation

### Why This Model Works

1. **Lumped Parameter Approach:** Complex 3D vascular network simplified to 4 nodes with equivalent resistances and capacitances
2. **Nonlinear Resistances:** Accounts for vessel collapse when transmural pressure is negative (IOP > vessel pressure)
3. **Time-Varying Input:** Realistic cardiac waveform drives the system
4. **Stiff ODE Solver:** BDF method handles the rapid changes during cardiac cycle

### Key Assumptions

1. Blood is Newtonian fluid (constant viscosity)
2. Vessels are elastic tubes with linear stress-strain relationship (Young's modulus)
3. Flow is laminar (Poiseuille's law applies)
4. Capacitances are constant (vessel compliance doesn't change)
5. Initial conditions depend only on IOP (from lookup table)

## References

- Sala_ThesisPhd: Source for Pin_Waveform model
- Table 1, Table 2, Table 9: Parameter values from original research
- Shimpatica model: Lumped parameter retinal hemodynamics model

