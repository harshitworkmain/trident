# TRIDENT Sub-Project Context & Agent Memory: Wearable Live Telemetry ML Predictive Engine

## 1. Sub-Project Overview & Agent Role Division

This document serves as the persistent memory and technical blueprint for the **TRIDENT Wearable Live Telemetry ML Predictive Model Sub-Project**.

### Agent Role Division
- **Gemini (System Architect & Planner)**:
  - Responsible for: Hardware specs analysis, system design, feature engineering matrix, physiological trauma mapping, dataset selection, architecture planning, edge-case safety net design, git portability strategy, and maintaining/updating this context memory document after every iteration.
  - **Constraint**: **NO code generation or script writing**. Gemini plans and designs only.
- **Claude Opus (Code Generator & Implementer)**:
  - Responsible for: Writing Python scripts (`dataset_fusion_synthesizer.py`, `train_wearable_model.py`, `wearable_model.py`), updating Flask backend routes in `main.py`, modifying Jinja2 HTML templates (`platform.html`), CSS/JS assets, and executing Git commits & pushes to GitHub.
  - **Constraint**: Executes code implementation based on the blueprints established in this document and `implementation_plan.md`.

---

## 2. Hardware Analysis & Portability Strategy (MSI Modern 14 C12M)

### Current Development Laptop System Context
- **CPU**: 12th Gen Intel Core i5-1235U (10 Cores / 12 Threads: 2 P-Cores + 8 E-Cores).
- **Physical System Memory**: **8 GB Soldered DDR4-3200 RAM (Non-upgradeable)**. Usable RAM $\approx 7.5\text{ GB}$.
- **GPU**: Intel Integrated Graphics (Alder Lake GT2), shared system memory (no discrete NVIDIA/AMD GPU).
- **Storage**: Micron 512GB NVMe SSD ($\approx 370\text{ GB}$ free ext4 space).
- **OS**: Ubuntu 22.04.5 LTS (x86_64), Linux kernel 6.8.0.

### Hardware Analysis & Training Deferral Decision
> [!IMPORTANT]
> **Decision: Defer Model Training to High-RAM / GPU Compute Machine**
> 
> Loading 2.7 GB `PPG_FieldStudy`, 17.6 GB `WESAD` pickles, and 104 MB `MIT-BIH` simultaneously into Python memory for sliding-window matrix creation exceeds the 7.5 GB usable physical RAM limit, risking Linux OOM crashes or severe SSD swap thrashing.
> 
> **Portability Workflow**:
> 1. All pre-training Python scripts (`dataset_fusion_synthesizer.py`, `train_wearable_model.py`, `wearable_model.py`), Flask backend routes (`main.py`), and frontend UI templates/styles (`platform.html`, `dashboard.js`, `main_styles.css`) will be completely coded, integrated, and verified on this machine by **Claude Opus**.
> 2. All code and documentation will be committed and pushed to GitHub (`harshitworkmain/trident`).
> 3. Training will be executed on a target high-RAM / GPU machine by pulling the repository and running `python src/ml/train_wearable_model.py`.

---

## 3. Benchmark Datasets Inventory & Direct URLs

The sub-project utilizes 4 open-source benchmark datasets stored locally at `/home/harshit/Documents/projects-all/trident/data/raw/wearable_ml_datasets/` plus 2 cloned GitHub repositories:

### A. Local Datasets & Direct Access URLs
1. **MIT-BIH Arrhythmia Database** (`mit-bih-arrhythmia-database-1.0.0/`):
   - 🔗 **Direct URL**: [https://physionet.org/content/mitdb/1.0.0/](https://physionet.org/content/mitdb/1.0.0/) (DOI: `10.13026/C2F305`)
   - 48 30-min ECG records for `CARDIAC_ARREST` (Moody & Mark 2001; Pollard et al. Nature Health 2026).
2. **WESAD** (`WESAD/`):
   - 🔗 **Direct URL**: [https://archive.ics.uci.edu/dataset/465/wesad+wearable+stress+and+affect+detection](https://archive.ics.uci.edu/dataset/465/wesad+wearable+stress+and+affect+detection) (DOI: `10.24432/C57K5T`)
   - 15 subjects, raw EDA/GSR, BVP/PPG, Accel for `ELEVATED_STRESS` (Schmidt et al. 2018).
3. **PPG-DaLiA** (`PPG_FieldStudy/`):
   - 🔗 **Direct URL**: [https://archive.ics.uci.edu/dataset/495/ppg+dalia](https://archive.ics.uci.edu/dataset/495/ppg+dalia) (DOI: `10.24432/C53890`)
   - 15 subjects, Empatica E4 wrist signals for `HEMORRHAGIC_SHOCK` & `HYPOTHERMIA_RISK` (Reiss et al. 2019).
4. **HIFD (HR + IMU Fall Detection)** (`HR_IMU_falldetection_dataset-master/`):
   - 🔗 **Direct Repository**: [https://github.com/nhoyh/HR_IMU_falldetection_dataset](https://github.com/nhoyh/HR_IMU_falldetection_dataset) (IEEE: `8970371`)
   - 📄 **Research Paper PDF**: [Cluster-Analysis-Based_User-Adaptive_Fall_Detection_Using_Fusion_of_Heart_Rate_Sensor_and_Accelerometer_in_a_Wearable_Device.pdf](file:///home/harshit/Documents/projects-all/trident/data/raw/wearable_ml_datasets/HR_IMU_falldetection_dataset-master/Cluster-Analysis-Based_User-Adaptive_Fall_Detection_Using_Fusion_of_Heart_Rate_Sensor_and_Accelerometer_in_a_Wearable_Device.pdf)
   - 21 subjects, raw `.mat` wrist Accel + Gyro + HR for `CONCUSSIVE_STASIS` & `CRUSH_ENTRAPMENT` (Nho et al. IEEE Access 2020).

### B. Remote GitHub Repositories
1. **SisFall Benchmark Repository**: 🔗 [https://github.com/mojtabaSefidi/Fall-Detection-System.git](https://github.com/mojtabaSefidi/Fall-Detection-System.git) (Cloned at `sisfall/`).
2. **UP-Fall Multimodal System**: 🔗 [https://github.com/jpnm561/HAR-UP.git](https://github.com/jpnm561/HAR-UP.git) (Cloned at `upfall/`).

---

## 4. Comprehensive 8-State Disaster Trauma Taxonomy

1. `0: STABLE`: Nominal vitals and physical movement.
2. `1: ELEVATED_STRESS`: Acute panic & autonomic shock ($GSR > 0.8$, elevated HR, normal $SpO_2$).
3. `2: HYPOTHERMIA_RISK`: Sub-zero glacial immersion ($BPM < 50$, falling $SpO_2$, shivering stasis).
4. `3: ASPIRATION_HYPOXIA`: Mud slurry aspiration / drowning ($\Delta SpO_2/\Delta t < -2.0\%/\text{s}$, $acc\_mag < 2.5g$).
5. `4: HEMORRHAGIC_SHOCK`: Arterial laceration / internal bleeding ($BPM > 130$, `pulse_amp_decay` $< 0.4$, high $GSR$).
6. `5: CONCUSSIVE_STASIS`: Head/spinal kinetic impact ($acc\_mag > 4.5g$, `motion_stasis` $< 0.02$).
7. `6: CRUSH_ENTRAPMENT`: Rubble/boulder collapse (`motion_stasis` $< 0.02$, `gps_displacement` $\approx 0$, sustained high $GSR$).
8. `7: CARDIAC_ARREST`: Electrocution / sudden pulse collapse (`pulse_amp` $\approx 0$ or extreme arrhythmia $BPM < 30 \text{ or } > 185$).

---

## 5. Feature Engineering, Dataset Fusion & Train-Test Split Specifications

### A. Dataset Harmonization & Attribute Consistency
When fusing multi-source datasets (`WESAD`, `PPG_FieldStudy`, `MIT-BIH Arrhythmia`, `HR_IMU_falldetection`, plus synthetic ATLS trauma trajectories), consistency across units, sampling rates, datatypes, and precision is enforced:
- **Baseline Time Grid**: All sensor streams are resampled to a **50 Hz uniform time grid** ($20\text{ ms}$ sampling step) via linear interpolation.
- **Memory Precision**: Internal feature matrices use explicit `float32` (single precision floating point) to optimize cache usage and prevent RAM overflow during array concatenation, with timestamps in `float64` Unix epoch milliseconds.
- **Unit & Attribute Standardization Table**:

| Attribute | Canonical Unit | Standard Range | Storage Type | Source Normalization Formula / Rule |
| :--- | :--- | :--- | :--- | :--- |
| `bpm_current` | Beats per Minute ($BPM$) | $30.0 - 220.0$ | `float32` | Raw ECG/PPG peak detection ($60 / RR_{sec}$) |
| `pulse_amp_decay` | Amplitude Ratio | $0.0 - 1.0$ | `float32` | $A_{\text{window\_peak}} / A_{\text{baseline\_peak}}$ ratio |
| `spo2_current` | Percentage ($\%$) | $0.0 - 100.0\%$ | `float32` | Red/IR AC/DC ratio from MAX30102 sensor |
| `acc_mag` | Force ($g$) | $0.0 - 16.0g$ | `float32` | $\sqrt{a_x^2 + a_y^2 + a_z^2} / 9.81$ (normalized to $1g = \text{Earth gravity}$) |
| `gyro_mag` | Angular Speed ($^\circ/\text{s}$) | $0.0 - 2000.0^\circ/\text{s}$ | `float32` | $\sqrt{g_x^2 + g_y^2 + g_z^2}$ |
| `gsr_stress_norm` | Normalized Conductance | $0.0 - 1.0$ | `float32` | Min-Max scaling of EDA skin conductance ($\mu\text{S}$) per subject |
| `gps_displacement_15s` | Distance ($m$) | $0.0 - 500.0m$ | `float32` | Haversine distance over 15s window |

---

### B. Missing Value Handling & Model-Based Imputation Strategy
1. **In-Stream Short Gaps ($< 2.0\text{ s}$)**: Caused by transient RF telemetry dropouts. Filled using continuous linear spline interpolation during parsing.
2. **Sensor Off / Disconnected ("No Finger" on MAX30102)**: When PPG/SpO2 drops due to sensor detachment or cardiac collapse ($SpO_2 = 0$), values are represented explicitly as `np.nan`.
3. **XGBoost Native Default Split Branching**: Rather than forcing artificial mean/median imputation that masks true sensor failure, XGBoost natively routes missing (`NaN`) feature values down dedicated default split branches learned during gradient boosting.
4. **Model-Based Imputation for Relational Pre-processing**: For statistical baseline calculations across incomplete historical windows, an Iterative Random Forest / KNN Regressor imputer is available to estimate baseline physiological metrics when required.

---

### C. Categorical Encoding Matrix
- **Target Variable (`health_state`)**: Encoded into 8 discrete ordinal integers (`0: STABLE` through `7: CARDIAC_ARREST`).
- **Device & Context Features**:
  - `sensor_location` (`wrist`, `chest`): One-Hot Encoded (`location_wrist`, `location_chest`).
  - `subject_posture` (`sitting`, `standing`, `lying`, `running`): One-Hot Encoded for multi-modal HAR baseline.
  - `subject_id`: Used exclusively as a grouping key for cross-validation splits (never passed directly to XGBoost to avoid patient ID overfitting).

---

### D. Feature Scaling (Tree-Based Invariance)
- Decision tree splits in XGBoost evaluate threshold inequalities ($x_i \ge \theta$). Monotonic scaling (MinMax, Standard Z-Score) has zero impact on decision tree split boundaries.
- Features are retained in their **raw physical units** ($BPM$, $\% SpO_2$, $g$) to preserve direct interpretability in SHAP tree explanations and clinical threshold safety rules.

---

### E. Time-Series Datetime & Temporal Features
- **Cyclical Hour Encoding**: $\sin(2\pi \cdot \text{hour}/24)$ and $\cos(2\pi \cdot \text{hour}/24)$ to capture circadian variations in resting heart rate and body temperature.
- **Elapsed Rescue Window ($\Delta t_{\text{elapsed}}$)**: Time passed since SOS trigger in seconds, capturing progressive systemic shock degradation.
- **Sample Gap Delta ($\Delta t_{\text{sample}}$)**: Duration between telemetry frames to measure network latency.

---

### F. Domain-Specific Interaction & Polynomial Features
Nonlinear relationships rooted in wilderness trauma physics:
1. **Kinetic-Stasis Coupling Index ($KSC$)**:
   $$KSC = \text{acc\_mag\_max\_3s} \times \frac{1}{\text{motion\_stasis} + 1e-5}$$
   *(High impact peak followed by immediate total immobility = Concussive Stasis / Traumatic Fall)*.

2. **Shock Severity Index ($SSI$)**:
   $$SSI = \frac{\text{bpm\_current}}{\text{spo2\_current} \times \text{pulse\_amp\_decay} + 1e-5}$$
   *(Elevated heart rate with collapsing SpO2 & PPG amplitude = Class III/IV Hemorrhagic Shock)*.

3. **Entrapment Isolation Marker ($EIM$)**:
   $$EIM = \frac{\text{gsr\_stress\_norm}}{\text{motion\_stasis} + \text{gps\_displacement\_15s} + 1e-5}$$
   *(High autonomic stress/GSR under zero physical movement or relocation = Rubble Entrapment)*.

4. **Polynomial Kinetic Energy Proxy**: $acc\_mag^2 = acc_x^2 + acc_y^2 + acc_z^2$.
5. **Heart Rate Acceleration**: $\frac{d(BPM)}{dt} \approx BPM_t - BPM_{t-1}$.

---

### G. Multimodal SOS Text Features
Distress text transcripts (e.g. from victim SOS voice input) are encoded into:
- **TF-IDF Keyword Vectors**: 20 top clinical disaster keywords (`trapped`, `bleeding`, `cold`, `unconscious`, `crush`, `chest`, `drowning`).
- **Transcript Derived Attributes**: `word_count`, `urgency_keyword_count`, `caps_ratio`.

---

### H. Statistical Aggregations (15-Second Window Matrix)
Computed across 750 samples per 15s window (50 Hz step):
1. `bpm_current`: Current instantaneous heart rate ($BPM$).
2. `bpm_mean_10s`: 15-second rolling mean heart rate.
3. `bpm_std_10s`: Heart rate variability ($\text{STD}$).
4. `pulse_amp_decay`: PPG amplitude ratio vs resting baseline ($0.0 - 1.0$).
5. `spo2_current`: Instantaneous blood oxygen percentage ($SpO_2$).
6. `spo2_slope`: Oxygen desaturation rate ($\Delta SpO_2 / \Delta t$).
7. `acc_mag_max_3s`: Peak acceleration over last 3s ($g$).
8. `motion_stasis`: Acceleration magnitude variance ($\text{Var}(acc\_mag)$).
9. `gsr_stress_norm`: Normalized skin conductance ($0.0 - 1.0$).
10. `gsr_slope`: Skin conductance rate of change ($\Delta GSR / \Delta t$).
11. `fall_flag`: Binary MPU6050 fall detection flag (`0` or `1`).
12. `gps_displacement_15s`: Displacement over 15 seconds (meters).

---

### I. Train-Test-Validation Split Methodology
To strictly prevent **data leakage** across sliding time-series windows:
1. **Subject-Wise GroupKFold Splitting**:
   - Time-series samples from the same subject/patient ($S_1 - S_{15}$ in WESAD/PPG-DaLiA) are grouped strictly into the *same* fold.
   - **No overlapping windows** from the same person exist across training, validation, or test sets.
2. **Split Proportions**:
   - **70% Training Set**: Model optimization and gradient boosting.
   - **15% Validation Set**: Early stopping evaluation (`early_stopping_rounds=15`, multi-class log loss monitoring).
   - **15% Holdout Test Set**: Blind final evaluation (Confusion Matrix, F1-Score per state, SHAP summary plots).
3. **Stratified Group Sampling**:
   - Synthetic trauma trajectories (ATLS Hemorrhagic Shock & Mud Aspiration desaturation) and rare benchmark classes (`CARDIAC_ARREST`, `CONCUSSIVE_STASIS`) are stratified evenly across subject folds to ensure every fold contains balanced representation of high-acuity states.

---


## 6. Sub-Project Technical Architecture & Execution Plan

### A. Data Fusion Synthesizer (`src/ml/dataset_fusion_synthesizer.py`)
- Fuses raw parser outputs from `WESAD`, `HR_IMU_falldetection`, `PPG_FieldStudy`, and `mitdb`.
- Generates synthetic ATLS Class I-IV Hemorrhagic Shock trajectories and Mud Aspiration desaturation curves ($N \approx 50,000$).

### B. XGBoost Model Training (`src/ml/train_wearable_model.py`)
- Script created and ready to run on high-spec compute target. Exports `src/ml/wearable_health_model.pkl` ($<0.5\text{ ms}$ inference).

### C. Backend API & Dynamic Priority Integration (`src/backend/main.py`)
- `POST /api/telemetry/wearable`: Runs `WearableHealthPredictor` inference, updates `wearable_telemetry` DB table.
- `calculate_priority()`: Dynamically elevates priority to 5 (CRITICAL) and triggers **Auto-ROV Scramble** when $R_{ML} \ge 0.75$ or high-acuity trauma states trigger.

### D. Command Dashboard UI (`platform.html`, `dashboard.js`, `main_styles.css`)
- Fixes SOS Modal OK button handler (`closeModal('successModal')`).
- Implements `TRIDENT_logo.png` branding across platform headers & browser tab favicon.
- Embeds real-time **AI Vitality Risk Radar** badge showing active health state and risk percentage.

---

## 7. Iteration Memory Log

| Date / Timestamp | Iteration Milestone | Summary of Decisions / Changes | Next Action |
| :--- | :--- | :--- | :--- |
| **2026-09-17** | Sub-Project Initialization & Memory Creation | Established agent roles (Gemini = Architect/Planner, Opus = Implementer/Coder). Validated 4 raw local datasets on disk (`WESAD`, `PPG_FieldStudy`, `MIT-BIH`, `HR_IMU_falldetection`). Defined 8-state disaster taxonomy & 12-feature matrix. | Created initial docs. |
| **2026-09-17** | Hardware Analysis & Portability Workflow Finalized | Analyzed laptop specs (MSI Modern 14, 8GB soldered RAM, i5-1235U). Agreed to defer actual training execution to a high-spec machine. Decided to write all pre-training code, backend routes, UI fixes, and push to GitHub for 100% portability. | Added direct dataset URLs to index docs & ready for Claude Opus implementation. |
| **2026-09-17** | Feature Engineering & Data Fusion Specs Detailed | Defined data unit harmonization (50Hz grid, `float32`), statistical window aggregations, 3 interaction features ($KSC, SSI, EIM$), missing value strategy (XGBoost native `NaN` default splits), and categorical encoding. | Ready for Claude Opus pre-training implementation & git push. |
