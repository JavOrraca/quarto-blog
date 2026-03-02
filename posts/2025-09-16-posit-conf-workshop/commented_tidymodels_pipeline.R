# Neural Network Hyperparameter Tuning with tidymodels
# This script demonstrates a complete ML pipeline using neural networks
# with hyperparameter tuning across multiple parameters including activation functions

library(tidymodels)
library(probably)
library(desirability2)

# Max's usual settings for consistent tidymodels behavior
tidymodels_prefer() # Resolves function conflicts in favor of tidymodels

# Set clean plotting theme and disable some console output for cleaner results
theme_set(theme_bw())
options(
  pillar.advice = FALSE, # Turn off tibble printing advice
  pillar.min_title_chars = Inf # Show full column names
)

# Check if PyTorch is available for neural network computations
if (torch::torch_is_installed()) {
  library(torch)
}

# ==============================================================================
# DATA LOADING AND SPLITTING
# ==============================================================================

# Load example classification dataset from tidymodels workshop
# This is a simulated dataset with class imbalance for demonstration
"https://raw.githubusercontent.com/tidymodels/" |>
  paste0("workshops/main/slides/class_data.RData") |>
  url() |>
  load()

# Create reproducible train/test split
set.seed(429)
sim_split <- initial_split(class_data, prop = 0.75, strata = class)
sim_train <- training(sim_split) # 75% for training
sim_test <- testing(sim_split) # 25% for final evaluation

# Set up 10-fold cross-validation for hyperparameter tuning
# Stratified sampling ensures balanced class representation in each fold
set.seed(523)
sim_rs <- vfold_cv(sim_train, v = 10, strata = class)

# ==============================================================================
# NEURAL NETWORK MODEL SPECIFICATION
# ==============================================================================

# Load brulee package for Torch-based neural networks in R
library(brulee)

rec <-
  recipe(class ~ ., data = sim_train) |>
  step_normalize(all_numeric_predictors())

# Define neural network model with multiple tunable hyperparameters
nnet_spec <-
  mlp(
    hidden_units = tune(), # Number of neurons in hidden layer(s)
    penalty = tune(), # L2 regularization strength (weight decay)
    learn_rate = tune(), # Learning rate for optimization
    epochs = 100, # Fixed number of training epochs
    activation = tune() # Activation function (ReLU, tanh, etc.)
  ) |>
  # brulee engine provides native PyTorch integration
  set_engine(
    "brulee",
    class_weights = tune(), # Handle class imbalance
    stop_iter = 10
  ) |> # Early stopping patience
  set_mode("classification")

# Create workflow combining preprocessing recipe with model spec
# Note: 'rec' should be defined earlier in your analysis - it's your preprocessing recipe
nnet_wflow <- workflow(rec, nnet_spec)
nnet_wflow

# ==============================================================================
# HYPERPARAMETER TUNING SETUP
# ==============================================================================

# Extract and customize parameter ranges for tuning
nnet_param <-
  nnet_wflow |>
  extract_parameter_set_dials() |>
  # Custom class weights: 1:50 ratio to handle severe class imbalance
  update(class_weights = class_weights(c(1, 50)))
nnet_param

# ==============================================================================
# PARALLEL PROCESSING SETUP
# ==============================================================================

# Set up parallel processing for faster hyperparameter tuning
cores <- parallelly::availableCores(logical = FALSE)

# Use mirai for efficient parallel processing (alternative to future)
library(mirai)
daemons(cores)

# Configure grid search controls
ctrl <- control_grid(
  save_pred = TRUE, # Save predictions for later analysis
  save_workflow = TRUE # Save fitted workflows for inspection
)

# Define comprehensive metrics for model evaluation
cls_mtr <- metric_set(
  brier_class, # Brier score (lower is better) - measures calibration
  roc_auc, # Area under ROC curve (higher is better)
  sensitivity, # True positive rate
  specificity # True negative rate
)

# ==============================================================================
# HYPERPARAMETER TUNING EXECUTION
# ==============================================================================

# Perform grid search across 25 parameter combinations
set.seed(12)
nnet_res <-
  nnet_wflow |>
  tune_grid(
    resamples = sim_rs, # Use 10-fold CV
    grid = 25, # Test 25 random parameter combinations
    param_info = nnet_param, # Use custom parameter ranges
    control = ctrl, # Save predictions and workflows
    metrics = cls_mtr # Evaluate using comprehensive metrics
  )

nnet_res

# ==============================================================================
# VISUALIZATION AND RESULTS ANALYSIS
# ==============================================================================

# 1. OVERALL PERFORMANCE OVERVIEW
# Default autoplot shows all metrics across hyperparameters
autoplot(nnet_res)
# This creates a grid of plots showing how each metric varies with each hyperparameter
# Look for parameters that consistently produce good performance across metrics

# 2. BRIER SCORE ANALYSIS (Calibration Focus)
autoplot(nnet_res, metric = "brier_class") +
  facet_grid(
    . ~ name,

    scale = "free_x"
  ) +
  lims(y = c(0.04, 0.22)) # Zoom in on reasonable range (excludes poor tanh results)

# Brier score measures both discrimination AND calibration
# Lower values indicate better-calibrated probability predictions
# Each facet shows how Brier score changes with different hyperparameters

# 3. ROC AUC ANALYSIS (Discrimination Focus)
autoplot(nnet_res, metric = "roc_auc") +
  facet_grid(. ~ name, scale = "free_x") +
  lims(y = c(0.83, 0.97)) # Focus on the performance range that matters

# ROC AUC measures the model's ability to distinguish between classes
# Values closer to 1.0 indicate better discrimination
# This plot helps identify which hyperparameters improve class separation

# 4. SENSITIVITY/SPECIFICITY TRADE-OFF
autoplot(nnet_res, metric = c("sensitivity", "specificity"))

# Shows the classic trade-off between true positive rate and true negative rate
# In class-imbalanced datasets, you often need to balance these carefully
# The plot helps visualize how hyperparameters affect this balance

# ==============================================================================
# DETAILED RESULTS INSPECTION
# ==============================================================================

# Summary statistics across all folds for each parameter combination
collect_metrics(nnet_res) |>
  relocate(.metric, mean) # Put metric name and average performance first

# Individual fold results (useful for understanding variability)
collect_metrics(nnet_res, summarize = FALSE) |>
  relocate(.metric, .estimate)

# ==============================================================================
# MODEL SELECTION AND FINAL EVALUATION
# ==============================================================================

# Identify top-performing parameter combinations based on Brier score
# Brier score is often preferred for classification as it rewards well-calibrated predictions
show_best(nnet_res, metric = "brier_class") |>
  relocate(.metric, mean)

# Select the single best parameter combination
nnet_best <- select_best(nnet_res, metric = "brier_class")
nnet_best

# ==============================================================================
# CALIBRATION ANALYSIS
# ==============================================================================

# Extract predictions from the best model for calibration assessment
nnet_holdout_pred <-
  nnet_res |>
  collect_predictions(parameters = nnet_best)

# Create a calibration plot to assess prediction reliability
nnet_holdout_pred |>
  cal_plot_windowed(
    truth = class,
    estimate = .pred_event,
    window_size = 0.2, # Each bin contains 20% of predictions
    step_size = 0.025, # Overlapping windows for smoother curve
  )
# This plot shows whether predicted probabilities match actual event rates
# Points close to the diagonal line indicate well-calibrated predictions
# Deviations suggest the model is over- or under-confident in its predictions

# ==============================================================================
# TUNING THE PROBABILITY THRESHOLD
# ==============================================================================

# Add an adjustment spec (to tune the prob threshold) via a tailor object
thrsh_tlr <-
  tailor() |>
  adjust_probability_threshold(threshold = tune())

# workflows v1.3.0 implemented {tailor}-based postprocessing
### Add your tailors as the third argument in the workflows object
nnet_wflow_thrsh <- workflow(rec, nnet_spec, thrsh_tlr)
nnet_wflow_thrsh

nnet_param_thresh <-
  nnet_wflow_thrsh |>
  extract_parameter_set_dials() |>
  # Tune over the probability threshold given the class imbalance (vs an adjustment of class weights or some other postprocessing)
  update(threshold = threshold(c(0.001, 0.5)))

nnet_param_thresh

# Perform grid search across 25 parameter combinations
set.seed(12)
nnet_res_thresh <-
  nnet_wflow_thrsh |>
  tune_grid(
    resamples = sim_rs, # Use 10-fold CV
    grid = 25, # Test 25 random parameter combinations
    param_info = nnet_param_thresh, # Use custom parameter ranges
    control = ctrl, # Save predictions and workflows
    metrics = cls_mtr # Evaluate using comprehensive metrics
  )

nnet_res_thresh

### now calibration using multi-metric optimization!
less_brier <-
  nnet_res_thresh |>
  select_best_desirability(
    minimize(brier_class)
  )

nnet_res_thresh |>
  collect_predictions(parameters = less_brier) |>
  cal_plot_windowed(
    truth = class,
    estimate = .pred_event,
    window_size = 0.2,
    step_size = 0.025,
  )

# ==============================================================================
# KEY TAKEAWAYS FROM THE VISUALIZATIONS:
# ==============================================================================

# 1. Overall Performance Plot:
#    - Shows how each hyperparameter affects model performance
#    - Look for consistent patterns across metrics
#    - Some activation functions may perform poorly (e.g., tanh in some cases)

# 2. Brier Score Plot:
#    - Focuses on prediction calibration
#    - Lower scores = better calibrated probabilities
#    - Important for when you need reliable probability estimates

# 3. ROC AUC Plot:
#    - Shows discrimination ability
#    - Higher values = better at separating classes
#    - May not tell the whole story with imbalanced data

# 4. Sensitivity/Specificity Plot:
#    - Critical for understanding the precision/recall trade-off
#    - In imbalanced datasets, optimizing for both can be challenging
#    - Shows which parameters help balance true positive vs true negative rates

# 5. Calibration Plot:
#    - Validates that probability predictions are trustworthy
#    - Essential for decision-making based on predicted probabilities
#    - Well-calibrated models have points close to the diagonal line

# 6. Tuning the Probability Threshold
