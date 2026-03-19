"""
Retinal Model Module - Wraps the retinal hemodynamics simulation.

This module wraps the existing retinal model code WITHOUT modifying
any of the mathematical/logical computations. Only the structure
is refactored to fit the pipeline framework.

All constants, equations, and calculations are IDENTICAL to the original
src/DT-OH/retinal-model.py file.
"""

import os
import json
import math
import warnings
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed

# Import BaseModule and the core RetinalModelModule logic
from .base_module import BaseModule

warnings.filterwarnings('ignore')


# ==========================================================
# MODEL CONSTANTS & PARAMETERS
# (IDENTICAL to original retinal-model.py - DO NOT MODIFY)
# ==========================================================

# Output pressure of the lumped modelp
P_out = 14.00

# Fixed Resistances [mm Hg s/mL] - Table 2
R_in = 2.25e4
R_1a = 4.30e3
R_1b = 4.30e3
R_2a = 6.00e3
R_2b = 6.00e3
R_3a = 5.68e3
R_3b = 5.68e3
R_5c = 1.35e3
R_5d = 1.35e3
R_out = 5.74e3
R_constT = R_1a + R_1b + R_2a + R_2b + R_3a + R_3b + R_5c + R_5d


# Parameters Values for variable resistances

v = 0.49                        # Wall Poission's ratio (Table 1/Table 9)

# CRA parameter values
mu_CRA_cP   = 3.0                                   # fluid viscosity [cP] - Table 1
mu_CRA      = mu_CRA_cP * 1e-3 * 0.00750062         # fluid viscosity: conversion from [cP] to [mmHg s] 
E_CRA_MPa   = 0.3                                   # Young Modulus [MPa] - Table 1
E_CRA       = E_CRA_MPa * 1e6 * 0.00750062          # Young Modulus: conversion from [MPa] to [mmHg] 
d_CRA_ref   = 175e-4                                # Refernce radius [cm] - Table 1
r_CRA_ref   = d_CRA_ref / 2
A_ref_CRA   = math.pi * r_CRA_ref**2                # Reference cross sectional area [cm^2] 
h_CRA       = 39.7239e-4                            # Thickness [cm] of vessel wall - Table 1
L_1c        = 0.2e-1                                # Lengths [cm] of segment c - Table 1
L_1d        = 1e-1                                  # Lengths [cm] of segment d - Table 1
K_l_CRA     = 12 * A_ref_CRA / (math.pi * h_CRA**2)       # [-]
K_p_CRA     = (1/12) * (E_CRA * h_CRA**3 / (1 - v**2)) * (math.pi / A_ref_CRA)**(3/2)  # [mmHg ]
k0_CRA_1c   = (A_ref_CRA**2) / (8 * math.pi * mu_CRA * L_1c)
k0_CRA_1d   = A_ref_CRA**2 / (8 * math.pi * mu_CRA * L_1d)


# CRV parameter values
mu_CRV_cP   = 3.24                          # fluid viscosity [cP] - Table 1
mu_CRV      = mu_CRV_cP * 1e-3 * 0.00750062     # fluid viscosity: conversion from [cP] to [mmHg s]
E_CRV_MPa   = 0.6                           # Young Modulus [MPa] - Table 1 
E_CRV = E_CRV_MPa * 1e6 * 0.00750062            # Young Modulus: conversion from [MPa] to [mmHg] Table 1 
d_CRV_ref = 238e-4                          # [cm]
r_CRV_ref = d_CRV_ref / 2                     # [cm] 
A_ref_CRV = math.pi * r_CRV_ref**2         # Reference cross sectional area [cm^2]
h_CRV = 10.7e-4                             # wall thickness [cm] - Table 1
L_5a = 1e-1                                 # Length of segment a [cm] - Table 1
L_5b = 0.2e-1                               # Length of segment b [cm] - Table 1
K_l_CRV = 12 * A_ref_CRV / (math.pi * h_CRV**2)
K_p_CRV = (1/12) * (E_CRV * h_CRV**3 / (1 - v**2)) * (math.pi / A_ref_CRV)**(3/2)
k0_CRV_5a = A_ref_CRV**2 / (8 * math.pi * mu_CRV * L_5a)
k0_CRV_5b = A_ref_CRV**2 / (8 * math.pi * mu_CRV * L_5b)


# venules parameter values
mu_VEN_cP   = 3.24                          # fluid viscosity [cP] - Matlab File
mu_VEN      = mu_VEN_cP * 1e-3 * 0.00750062     # fluid viscosity: conversion from [cP] to [mmHg s]
E_VEN_MPa   = 0.066                         # Young Modulus [Mpa] -  Table 9 
E_VEN       = E_VEN_MPa * 1e6 * 0.00750062      # Young Modulus: conversion from [Pa] to [mmHg] 
d_VEN_ref   = 0.015476685724901             # equivalent diameter [cm] - Matlab File
r_VEN_ref   = d_VEN_ref / 2
A_ref_VEN   = math.pi * r_VEN_ref**2       # Reference cross sectional area [cm^2]
h_VEN       = d_VEN_ref / 20               # wall thickness [cm] -  Table 9 
L_VEN       = 0.413520                     # equivalent length [cm] - Matlab File
L_4a        = L_VEN / 2                      # [cm]
L_4b        = L_VEN / 2                      # [cm] 
K_l_VEN     = 12 * A_ref_VEN / (math.pi * h_VEN**2)
K_p_VEN     = (1/12) * (E_VEN * h_VEN**3 / (1 - v**2)) * (math.pi / A_ref_VEN)**(3/2)
k0_VEN_4a   = A_ref_VEN**2 / (8 * math.pi * mu_VEN * L_4a)
k0_VEN_4b   = A_ref_VEN**2 / (8 * math.pi * mu_VEN * L_4b)

# definition of capacitance

C1 = 7.22 * 10**(-7)     # mL/mmHg
C2 = 7.53 * 10**(-7)     # mL/mmHg
C4 = 1.67 * 10**(-5)     # mL/mmHg
C5 = 1.07 * 10**(-5)     # mL/mmHg


# ==========================================================
# CORE FUNCTIONS (IDENTICAL to original - DO NOT MODIFY)
# ==========================================================

# Global variables used by the ODE solver
T = []
Pin = []
R1c = []
R1d = []
R4a = []
R4b = []
R5a = []
R5b = []
Q1d = []
Q4a = []
Q4b = []
Q5a = []
Q5b = []


def Pin_Waveform(time, c):
    
    global Thr
    
    # Definition Variable
     
    SP = c[0]
    DP = c[1]
    HR = c[3]  # Use actual heart rate from input
    Thr = 60 / HR  
    Tm = time % Thr
    
    # Computation Pin
    
    if Tm <= 0.082 * Thr:
        v = 0.65 * SP - 0.475 * DP * math.sin((2 * math.pi * Tm / (4 * 0.082 * Thr))
            + (2 * math.pi * 0.082 * Thr / (0.328 * Thr)))
        
    elif ((Tm > 0.082 * Thr) and (Tm <= 0.112 * Thr)):
        v = 0.65 * SP + 0.9 * math.sin((2 * math.pi * Tm / (0.03 * Thr))
            - (2 * math.pi * 0.082 * Thr / (0.03 * Thr)))
    
    elif ((Tm > 0.112 * Thr) and (Tm <= 0.398 * Thr)):
        v = 0.65 * SP + 0.118 * SP * math.sin((2 * math.pi * Tm / (0.572 * Thr))
            - (2 * math.pi * 0.112 * Thr / (0.572 * Thr)))    
        
    elif ((Tm > 0.398 * Thr) and (Tm <= 0.432 * Thr)):   
        v = -(0.13 * SP * Tm / (0.034 * Thr)) + 0.65 * SP + (0.13 * SP * 0.398 * Thr / (0.034 * Thr))
        
    elif ((Tm > 0.432 * 60 / HR) and (Tm <= 0.482 * 60 / HR)):
        v = (0.52 * SP - 0.8 * math.sin((2 * math.pi * Tm / (0.05 * Thr)) + (2 * math.pi * 0.332 * Thr / (0.05 * Thr))))

    else:
        v = (0.52 * SP + (0.52 * SP - 0.5 * DP) * math.sin((2 * math.pi * Tm / (2.072 * Thr)) + (2 * math.pi * 0.554 * Thr / (2.072 * Thr))))
        
    return v


def f(time, P, c):
    """Calculates and returns flux (ODE right-hand side)."""
    
    global R_4a, R_4b, R_5a, R_5b, QR
    global Pin, Q1d, Q4a, Q4b, Q5a, Q5b 

    # Define initial condition
    P1 = P[0]
    P2 = P[1]
    P4 = P[2]
    P5 = P[3]
    
    # Save Global variable of interest
    
    T.append(time)
    Pin.append(Pin_Waveform(time, c))
    
    # definition of capacitance
    
    C1 = 7.22 * 10**(-7)     # mL/mmHg
    C2 = 7.53 * 10**(-7)     # mL/mmHg
    C4 = 1.67 * 10**(-5)     # mL/mmHg
    C5 = 1.07 * 10**(-5)     # mL/mmHg
    
    # definition of transmural pressures   (c[2] is IOP)
    
    deltaP1c = P1 - c[2]
    deltaP1d = P1 - c[2]
    deltaP4a = P4 - c[2]
    deltaP4b = P4 - c[2]
    deltaP5a = P5 - c[2]
    deltaP5b = P5 - c[2]
    
    # definition of variable resistances - CRA
    
    R_1c = (1 / k0_CRA_1c) * (1 + deltaP1c / (K_p_CRA * K_l_CRA))**(-4)
    R_1d = (1 / k0_CRA_1d) * (1 + deltaP1d / (K_p_CRA * K_l_CRA))**(-4)
    
    # definition of variable resistances - venules and CRV
    
    if deltaP4a >= 0:
        R_4a = (1 / k0_VEN_4a) * (1 + deltaP4a / (K_p_VEN * K_l_VEN))**(-4)
    else:
        R_4a = (1 / k0_VEN_4a) * (1 - deltaP4a / (K_p_VEN))**(4/3)

    if deltaP4b >= 0:
        R_4b = (1 / k0_VEN_4b) * (1 + deltaP4b / (K_p_VEN * K_l_VEN))**(-4)
    else:
        R_4b = (1 / k0_VEN_4b) * (1 - deltaP4b / (K_p_VEN))**(4/3)
    
    if deltaP5a >= 0:
        R_5a = (1 / k0_CRV_5a) * (1 + deltaP5a / (K_p_CRV * K_l_CRV))**(-4)
    else:
        R_5a = (1 / k0_CRV_5a) * (1 - deltaP5a / (K_p_CRV))**(4/3)
    
    if deltaP5b >= 0:    
        R_5b = (1 / k0_CRV_5b) * (1 + deltaP5b / (K_p_CRV * K_l_CRV))**(-4)
    else:         
        R_5b = (1 / k0_CRV_5b) * (1 - deltaP5b / (K_p_CRV))**(4/3)
        
    # definition of nonlinear system  
    
    F1 = ((Pin_Waveform(time, c) - P1) / (R_in + R_1a) - (P1 - P2) / (R_1b + R_1c + R_1d + R_2a)) / C1
    F2 = ((P1 - P2) / (R_1b + R_1c + R_1d + R_2a) - (P2 - P4) / (R_2b + R_3a + R_3b + R_4a)) / C2
    F3 = ((P2 - P4) / (R_2b + R_3a + R_3b + R_4a) - (P4 - P5) / (R_4b + R_5a + R_5b + R_5c)) / C4
    F4 = ((P4 - P5) / (R_4b + R_5a + R_5b + R_5c) - (P5 - P_out) / (R_5d + R_out)) / C5
    
    # ==================================================
    # Saving Part for resistances and  fluxes
    # ==================================================
    
    # =====================
    
    # Resistances
    
    R1c.append(R_1c)
    R1d.append(R_1d)
    R4a.append(R_4a)
    R4b.append(R_4b)
    R5a.append(R_5a)
    R5b.append(R_5b)
    
    # =====================
    # Fluxes
    
    Q1d.append(deltaP1d / R_1d)
    Q4a.append(deltaP4a / R_4a)
    Q4b.append(deltaP4b / R_4b)
    Q5a.append(deltaP5a / R_5a)
    Q5b.append(deltaP5b / R_5b)
    
    # final definition of function 

    F = [F1, F2, F3, F4]
    
    # returns the calculated derivatives of the state variables F1-F4
    return F


def PostProcessing(t, P, c):
    """Computation of the output utilizing vectorized function to speed up the code."""
    
    # Computation of the input pressure 
    
    Pin = [Pin_Waveform(i, c) for i in t]
    # Delta pressures
   
    deltaP1c = P[0] - c[2]
    deltaP1d = P[0] - c[2]
    deltaP4a = P[2] - c[2]
    deltaP4b = P[2] - c[2]
    deltaP5a = P[3] - c[2]
    deltaP5b = P[3] - c[2]
    
    # Computation of the resistances 
    
    R_1c = [(1 / k0_CRA_1c) * (1 + dp1c / (K_p_CRA * K_l_CRA))**(-4) for dp1c in deltaP1c]
    R_1d = [(1 / k0_CRA_1d) * (1 + dp1d / (K_p_CRA * K_l_CRA))**(-4) for dp1d in deltaP1d]
    
    
    R_4a = [(1 / k0_VEN_4a) * (1 + dp4a / (K_p_VEN * K_l_VEN))**(-4) if dp4a >= 0 else
            (1 / k0_VEN_4a) * (1 - dp4a / (K_p_VEN))**(4/3) for dp4a in deltaP4a] 
    R_4b = [(1 / k0_VEN_4b) * (1 + dp4b / (K_p_VEN * K_l_VEN))**(-4) if dp4b >= 0 else
            (1 / k0_VEN_4b) * (1 - dp4b / (K_p_VEN))**(4/3) for dp4b in deltaP4b] 
    R_5a = [(1 / k0_CRV_5a) * (1 + dp5a / (K_p_CRV * K_l_CRV))**(-4) if dp5a >= 0 else
            (1 / k0_CRV_5a) * (1 - dp5a / (K_p_CRV))**(4/3) for dp5a in deltaP5a] 
    R_5b = [(1 / k0_CRV_5b) * (1 + dp5b / (K_p_CRV * K_l_CRV))**(-4) if dp5b >= 0 else
            (1 / k0_CRV_5b) * (1 - dp5b / (K_p_CRV))**(4/3) for dp5b in deltaP5b] 
    
    # Computation of the volume flow rates 
      
    Qin = [(Pin_Waveform(t, c) - p1) / (R_in + R_1a) for t, p1 in zip(t, P[0])] 
    Q12 = [(p1 - p2) / (R_1b + r1c + r1d + R_2a) for (p1, p2, r1c, r1d) in zip(P[0], P[1], R_1c, R_1d)]
    Q24 = [(p2 - p4) / (R_2b + R_3a + R_3b + r4a) for (p2, p4, r4a) in zip(P[1], P[2], R_4a)]
    Q45 = [(p4 - p5) / (r4b + r5a + r5b + R_5c) for (p4, p5, r4b, r5a, r5b) in zip(P[2], P[3], R_4b, R_5a, R_5b)]
    Qout = [(p5 - P_out) / (R_5d + R_out) for p5 in P[3]]
    
    # Compute of the variables needed for RNN analysis

    F1 = [(qin - q12) / C1 for (qin, q12) in zip(Qin, Q12)]
    F2 = [(q12 - q24) / C2 for (q12, q24) in zip(Q12, Q24)]
    F3 = [(q24 - q45) / C4 for (q24, q45) in zip(Q24, Q45)]
    F4 = [(q45 - qout) / C5 for (q45, qout) in zip(Q45, Qout)]   
  
    
    # Organize the variable into list
    F = {'F1': F1, 'F2': F2, 'F3': F3, 'F4': F4}
    Q = {'Qin': np.asarray(Qin), 'Q12': np.asarray(Q12), 'Q24': np.asarray(Q24), 'Q45': np.asarray(Q45), 'Qout': (Qout)}
    R = {'R_1c': np.asarray(R_1c), 'R_1d': np.asarray(R_1d), 'R_4a': np.asarray(R_4a), 'R_4b': np.asarray(R_4b), 'R_5a': np.asarray(R_5a), 'R_5b': np.asarray(R_5b)}

    return Pin, F, Q, R


# ==========================================================
# MODULE CLASS
# ==========================================================

class RetinalModelModule(BaseModule):
    """
    Retinal hemodynamics simulation module.
    
    Wraps the Shimpatica lumped parameter model for retinal blood flow.
    All mathematical computations are IDENTICAL to the original implementation.
    """
    
    # Default output columns
    RESULT_COLS = ['P1', 'P2', 'P4', 'P5', 'Qmean', 'R1', 'R4', 'R5']
    
    # Default required columns
    REQUIRED_COLS = ['SBP', 'DBP', 'IOP', 'HR']
    
    def __init__(
        self, 
        name: str, 
        config: Dict[str, Any], 
        output_dir: Path,
        logs_dir: Optional[Path] = None,
        checkpoints_dir: Optional[Path] = None
    ):
        """
        Initialize the retinal model module.
        
        Args:
            name: Module name
            config: Module configuration from YAML
            output_dir: Output directory for results
            logs_dir: Directory for logs (optional)
            checkpoints_dir: Directory for checkpoints (optional)
        """
        super().__init__(name, config, output_dir, logs_dir, checkpoints_dir)
        
        # Resolve initial conditions file path from config
        initial_conditions_path = config.get(
            'initial_conditions_path',
            'src/modules/DT_OH/init/Initial_wIOP.csv'
        )
        
        # Resolve path relative to project root if not absolute
        if not Path(initial_conditions_path).is_absolute():
            # Try to resolve relative to project root
            project_root = Path(__file__).parent.parent.parent.parent
            initial_conditions_path = project_root / initial_conditions_path
        else:
            initial_conditions_path = Path(initial_conditions_path)
        
        self.initial_conditions_path = str(initial_conditions_path)
        
        # Processing parameters
        processing = config.get('processing', {})
        self.n_workers = processing.get('n_workers', None)
        self.checkpoint_interval = processing.get('checkpoint_interval', 1)
        
        # Patient ID column (optional)
        self.patient_id_column = config.get('patient_id_column', 'Patient')
        
        # Load initial conditions data
        self._load_initial_conditions()
    
    def _load_initial_conditions(self):
        """Load the initial conditions lookup table."""
        try:
            self._iop_data = pd.read_csv(self.initial_conditions_path)
            self.logger.info(f"Loaded initial conditions from {self.initial_conditions_path}")
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Initial conditions file not found: {self.initial_conditions_path}"
            )
    
    def get_output_columns(self) -> List[str]:
        """Return output column names."""
        return self.config.get('output_columns', self.RESULT_COLS)
    
    def get_required_columns(self) -> List[str]:
        """Return required input column names."""
        return self.config.get('required_columns', self.REQUIRED_COLS)
    
    def _sel_InCond(self, IOP: float) -> List[float]:
        """
        Select initial conditions based on IOP value.
        IDENTICAL to original sel_InCond function.
        """
        FilterIOP = self._iop_data[self._iop_data['IOP'] == np.rint(IOP)]
        P1 = float(FilterIOP['P1'])
        P2 = float(FilterIOP['P2'])
        P4 = float(FilterIOP['P4'])
        P5 = float(FilterIOP['P5'])
        P0 = [P1, P2, P4, P5]
        return P0
    
    def _shimpatica_func(self, row: pd.Series) -> Tuple[float, ...]:
        """
        Core simulation function.
        IDENTICAL to original Shimpatica_Func.
        """
        P0 = self._sel_InCond(row['IOP'])
        Pinput = [row['SBP'],
                  row['DBP'],
                  row['IOP'],
                  row['HR']]

        Tc = 60 / Pinput[-1]
        Tfin = Tc * 10
        
        fR = solve_ivp(lambda t, y: f(t, y, Pinput), (0, Tfin), P0, method='BDF', atol=1e-8, rtol=1e-8)

        if fR.success == True:
            pass
        else:
            patient_id = row.get(self.patient_id_column, 'Unknown')
            self.logger.error(f'Patient {patient_id} FAILED: {fR.message}')
            raise Exception(f"Simulation failed for Patient {patient_id}: {fR.message}")
        
        Pin_out, F, Q, R = PostProcessing(fR.t, fR.y, Pinput)
        
        indexLastCycle = np.where(fR.t > Tc * 9)
        
        HeadP = ['P1', 'P2', 'P4', 'P5']
        HeadR = ['R_1c', 'R_1d', 'R_4a', 'R_4b', 'R_5a', 'R_5b']
        HeadQ = ['Q12', 'Q24', 'Q45']

        timeLastCycle = fR.t[indexLastCycle]

        valP = [[min(item[indexLastCycle]), max(item[indexLastCycle]), np.trapz(item[indexLastCycle], x=timeLastCycle) / (timeLastCycle[-1] - timeLastCycle[0])] for item in fR.y]
        timeP = [[np.argmin(item[indexLastCycle]), np.argmax(item[indexLastCycle])] for item in fR.y]

        valQ = [[min(Q[item][indexLastCycle]),
               max(Q[item][indexLastCycle]),
               np.trapz(Q[item][indexLastCycle], x=timeLastCycle) / (timeLastCycle[-1] - timeLastCycle[0])] 
               for item in HeadQ]

        timeQ = [[np.argmin(Q[item][indexLastCycle]),
                   np.argmax(Q[item][indexLastCycle])] 
                   for item in HeadQ]
                   
        valR = [[min(R[item][indexLastCycle]),
                   max(R[item][indexLastCycle]),
                   np.trapz(R[item][indexLastCycle], x=timeLastCycle) / (timeLastCycle[-1] - timeLastCycle[0])]
                   for item in HeadR]
        
        timeR = [[np.argmin(R[item][indexLastCycle]),
                   np.argmax(R[item][indexLastCycle])] 
                   for item in HeadR]

        P1sys, P2sys, P4sys, P5sys = [item[1] for item in valP]
        P1dis, P2dis, P4dis, P5dis = [item[0] for item in valP]
        P1mean, P2mean, P4mean, P5mean = [item[2] for item in valP]
        Q12sys, Q24sys, Q45sys = [item[1] for item in valQ]
        Q12dis, Q24dis, Q45dis = [item[0] for item in valQ]
        Q12mean, Q24mean, Q45mean = [item[2] for item in valQ]
        
        Qmean = (Q12mean + Q24mean + Q45mean) / 3.0
        
        R1csys, R1dsys, R4asys, R4bsys, R5asys, R5bsys = [item[0] for item in valR]
        R1cdis, R1ddis, R4adis, R4bdis, R5adis, R5bdis = [item[1] for item in valR]
        R1cmean, R1dmean, R4amean, R4bmean, R5amean, R5bmean = [item[2] for item in valR]
        
        R5 = np.trapz([R5amean, R5bmean, R_5c, R_5d])
        R1 = np.trapz([R1cmean, R1dmean, R_1a, R_1b])
        
        R4 = R4amean + R4bmean
        
        return P1mean, P2mean, P4mean, P5mean, Qmean, R1, R4, R5
    
    def process(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Process the input data through the retinal model.
        
        Args:
            data: Input DataFrame with required columns
            
        Returns:
            DataFrame with original columns plus computed results
        """
        self.logger.info(f"Starting processing of {len(data)} rows")
        
        # Validate inputs
        self.validate_inputs(data)
        
        # Add original index for tracking
        data = data.reset_index(drop=False).rename(columns={'index': '__orig_index__'})
        
        # Identify rows with missing required inputs
        required = self.get_required_columns()
        mask_missing = data[required].isna().any(axis=1)
        missing_df = data.loc[mask_missing].copy()
        
        if not missing_df.empty:
            self.logger.warning(f"Found {len(missing_df)} rows with missing required inputs")
            self.log_missing_data(missing_df)
        
        data_clean = data.loc[~mask_missing].copy()
        
        # Load checkpoint
        ckpt = self.load_checkpoint()
        processed_set = set(ckpt.get("processed_indices", []))
        
        # Filter already processed rows
        to_process = data_clean[~data_clean['__orig_index__'].isin(processed_set)].copy()
        
        if to_process.empty:
            self.logger.info("All rows already processed (from checkpoint)")
            # Load and return existing results
            results_file = self.results_dir / "results.csv"
            if results_file.exists():
                return pd.read_csv(results_file)
            return data_clean
        
        self.logger.info(f"Processing {len(to_process)} rows ({len(processed_set)} already done)")
        
        # Prepare output columns
        result_cols = self.get_output_columns()
        
        # Ensure header exists
        out_header_df = pd.concat(
            [to_process.head(0),
             pd.DataFrame(columns=result_cols)],
            axis=1
        )
        results_file = self.results_dir / "results.csv"
        if not results_file.exists():
            out_header_df.to_csv(results_file, index=False)
        
        # Process rows
        records = to_process.to_dict(orient='records')
        buffer_rows = []
        
        with ProcessPoolExecutor(max_workers=self.n_workers) as ex:
            futures = {
                ex.submit(self._run_on_row, rec): rec
                for rec in records
            }
            
            pbar = tqdm(total=len(futures), desc=f"Processing {self.name}")
            
            for fut in as_completed(futures):
                rec = futures[fut]
                try:
                    idx, result_vals = fut.result()
                except Exception as e:
                    patient_id = rec.get(self.patient_id_column, 'Unknown')
                    self.logger.error(f"Error processing Patient {patient_id}: {e}")
                    err_row = {k: rec.get(k, None) for k in ['__orig_index__', self.patient_id_column] + required}
                    err_row['error'] = str(e)
                    self.log_error(err_row)
                    pbar.update(1)
                    continue
                
                # Build output row
                out_row = pd.DataFrame([{**rec, **dict(zip(result_cols, result_vals))}])
                buffer_rows.append(out_row)
                
                # Checkpoint
                if len(buffer_rows) >= self.checkpoint_interval:
                    batch = pd.concat(buffer_rows, ignore_index=True)
                    cols_order = list(to_process.columns) + result_cols
                    batch = batch[cols_order]
                    
                    self.append_results(batch)
                    processed_set.update(batch['__orig_index__'].tolist())
                    self.save_checkpoint(sorted(list(processed_set)))
                    
                    buffer_rows.clear()
                
                pbar.update(1)
            
            pbar.close()
        
        # Final flush
        if buffer_rows:
            batch = pd.concat(buffer_rows, ignore_index=True)
            cols_order = list(to_process.columns) + result_cols
            batch = batch[cols_order]
            self.append_results(batch)
            processed_set.update(batch['__orig_index__'].tolist())
            self.save_checkpoint(sorted(list(processed_set)))
        
        # Load and return all results
        results_df = pd.read_csv(results_file)
        
        self.logger.info(f"Processing complete. Total rows: {len(results_df)}")
        
        return results_df
    
    def _run_on_row(self, row_dict: Dict) -> Tuple[int, List[float]]:
        """
        Helper to run simulation on a single row.
        Used for parallel processing.
        """
        row = pd.Series(row_dict)
        res = self._shimpatica_func(row)
        return row['__orig_index__'], list(res)


# ==========================================================
# WRAPPER CLASS FOR NEW ORCHESTRATOR INTERFACE
# ==========================================================

class RetinalModelModuleWrapper:
    """
    Wrapper class that adapts RetinalModelModule to the new orchestrator interface.
    
    The new orchestrator expects modules with:
    - __init__(config: Dict) where config contains 'input', 'output', and 'config' sections
    - run() method that processes files
    """
    
    def __init__(self, module_def: Dict[str, Any]):
        """
        Initialize the wrapper from module definition.
        
        Args:
            module_def: Module definition from pipeline config with 'input', 'output', 'config' sections
        """
        self.module_def = module_def
        self.name = module_def.get('name', 'RetinalModel')
        
        # Extract config sections (make copies to avoid modifying original)
        import copy
        input_conf = module_def.get('input', {})
        output_conf = module_def.get('output', {})
        module_config = copy.deepcopy(module_def.get('config', {}))
        
        # Resolve paths
        project_root = Path(__file__).parent.parent.parent.parent
        
        # Input CSV path
        csv_path = input_conf.get('csv_path', '')
        if not Path(csv_path).is_absolute():
            csv_path = project_root / csv_path
        else:
            csv_path = Path(csv_path)
        self.csv_path = csv_path
        
        # Output directory
        output_dir = output_conf.get('base_dir', 'output/DT_OH')
        if not Path(output_dir).is_absolute():
            output_dir = project_root / output_dir
        else:
            output_dir = Path(output_dir)
        self.output_dir = output_dir
        
        # Create subdirectories
        self.results_dir = self.output_dir
        self.logs_dir = self.output_dir / "logs"
        self.checkpoints_dir = self.output_dir / "checkpoints"
        
        # Create the actual RetinalModelModule instance
        # Resolve initial_conditions_path in module_config if relative
        if 'initial_conditions_path' in module_config:
            ic_path = module_config['initial_conditions_path']
            if not Path(ic_path).is_absolute():
                module_config['initial_conditions_path'] = str(project_root / ic_path)
        
        self.module = RetinalModelModule(
            name=self.name,
            config=module_config,
            output_dir=self.results_dir,
            logs_dir=self.logs_dir,
            checkpoints_dir=self.checkpoints_dir
        )
    
    def run(self):
        """
        Run the retinal model processing.
        
        Reads CSV from input path, processes it, and saves results.
        """
        print(f"--- Starting Task: {self.name} ---")
        
        # Load input CSV
        if not self.csv_path.exists():
            raise FileNotFoundError(f"Input CSV not found: {self.csv_path}")
        
        print(f"Loading input data from {self.csv_path}")
        data = pd.read_csv(self.csv_path)
        print(f"Loaded {len(data)} rows")
        
        # Process data
        results = self.module.process(data)
        
        # Results are already saved by the module's process() method
        print(f"Processing complete. Results saved to {self.results_dir}")
        print(f"--- Completed Task: {self.name} ---")

