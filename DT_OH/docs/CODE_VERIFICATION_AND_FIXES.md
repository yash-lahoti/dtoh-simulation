# Code Verification and Recommended Fixes

## Verification Summary

After comparing our implementation (`src/modules/DT-OH/inference.py`) with the original model (`eye-model.py`), I've verified that **all mathematical computations are identical** except for the issues documented below.

## ✅ Verified Identical Components

1. **All Constants:** Resistance values, capacitances, material properties (CRA, CRV, venules)
2. **Pin_Waveform Function:** All 6 piecewise segments match exactly
3. **f() Function (ODE):** All equations, resistance calculations, and variable updates match
4. **PostProcessing Function:** Delta pressure calculations, flow calculations match
5. **Output Extraction:** Statistics calculations (min/max/mean/trapz) match exactly

## ⚠️ Issues Found

### Issue 1: PostProcessing R_4b Uses Wrong Constant

**Location:** `PostProcessing()` function, lines 297-298

**Current Code (matches original bug):**
```python
R_4b = [(1 / k0_VEN_4a) * (1 + dp4b / (K_p_VEN * K_l_VEN))**(-4) if dp4b >= 0 else
        (1 / k0_VEN_4a) * (1 - dp4b / (K_p_VEN))**(4/3) for dp4b in deltaP4b]
```

**Problem:** Uses `k0_VEN_4a` instead of `k0_VEN_4b`

**Evidence:**
- In `f()` function (line 221-223), R_4b correctly uses `k0_VEN_4b`
- `k0_VEN_4a` and `k0_VEN_4b` are different because `L_4a = L_4b = L_VEN/2`, but they should still use their respective constants
- The original `eye-model.py` also has this bug (line 282-283)

**Impact:**
- Affects R4 calculations in post-processing
- May affect Q24 and Q45 flow rate calculations
- **Note:** The ODE solution itself is correct because `f()` uses the right constant

**Recommended Fix:**
```python
R_4b = [(1 / k0_VEN_4b) * (1 + dp4b / (K_p_VEN * K_l_VEN))**(-4) if dp4b >= 0 else
        (1 / k0_VEN_4b) * (1 - dp4b / (K_p_VEN))**(4/3) for dp4b in deltaP4b]
```

### Issue 2: Heart Rate Hardcoded in Pin_Waveform

**Location:** `Pin_Waveform()` function, line 144

**Current Code (matches original):**
```python
HR = 80
# HR = c[3]  # Commented out
```

**Problem:** Heart rate is hardcoded to 80 bpm instead of using actual patient HR

**Impact:**
- All patients simulated with 80 bpm regardless of actual HR
- Affects cardiac cycle timing (Thr = 60/HR)
- Affects waveform shape and timing

**Recommended Fix:**
```python
HR = c[3]  # Use actual heart rate from input
```

**Note:** The original code has `HR = 80` hardcoded, but `c[3]` contains the actual HR value.

## Recommended Action Plan

### Option A: Fix Both Issues (Recommended for Accuracy)

Fix both the R_4b constant and use actual HR. This will make the model more accurate while maintaining mathematical correctness.

### Option B: Match Original Exactly

Keep both bugs to exactly match the original implementation. This ensures identical results to the original code but may not be physically accurate.

### Option C: Fix Only R_4b

Fix the R_4b bug (more critical) but keep HR hardcoded to match original behavior.

## Implementation

If you choose to fix Issue 1, update `PostProcessing()` in `src/modules/DT-OH/inference.py`:

```python
# Line 297-298: Change k0_VEN_4a to k0_VEN_4b
R_4b = [(1 / k0_VEN_4b) * (1 + dp4b / (K_p_VEN * K_l_VEN))**(-4) if dp4b >= 0 else
        (1 / k0_VEN_4b) * (1 - dp4b / (K_p_VEN))**(4/3) for dp4b in deltaP4b]
```

If you choose to fix Issue 2, update `Pin_Waveform()` in `src/modules/DT-OH/inference.py`:

```python
# Line 144: Change from HR = 80 to HR = c[3]
HR = c[3]  # Use actual heart rate from input
```

## Verification

After making fixes, verify:
1. R_4b calculation in PostProcessing uses `k0_VEN_4b`
2. Pin_Waveform uses `c[3]` for HR (if fixing Issue 2)
3. All other calculations remain unchanged
4. Run test cases to ensure results are reasonable

