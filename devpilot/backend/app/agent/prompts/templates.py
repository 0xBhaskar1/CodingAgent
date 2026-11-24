REQUIREMENTS_ANALYSIS_PROMPT = (
    "Analyze the following software task and extract requirements:\n\n"
    "Task Description:\n{task_description}\n\n"
    "Provide a structured breakdown including project objective, functional requirements, "
    "technical requirements, required files, dependencies, and testing requirements."
)

PLANNER_PROMPT = (
    "Based on these requirements, create a structured implementation plan:\n\n"
    "Task Description:\n{task_description}\n\n"
    "Requirements:\n{requirements}\n\n"
    "Generate sequential tasks with task IDs, descriptions, required files, dependencies, and expected outcomes."
)

CODE_GENERATION_PROMPT = (
    "Generate complete production-grade source code for this task:\n\n"
    "Task:\n{task_description}\n\n"
    "Current Planned Step:\n{step_description}\n\n"
    "Target File:\n{target_file}\n\n"
    "Requirements:\n{requirements}\n\n"
    "Return complete file contents without placeholders or omissions."
)

ERROR_ANALYSIS_PROMPT = (
    "Analyze this command execution failure:\n\n"
    "Command:\n{command}\n\n"
    "Exit Code:\n{exit_code}\n\n"
    "Stdout:\n{stdout}\n\n"
    "Stderr:\n{stderr}\n\n"
    "Determine failure summary, failing files, root cause, and whether it is fixable."
)

CODE_REPAIR_PROMPT = (
    "Propose targeted code repairs for the following execution errors:\n\n"
    "Failing Files:\n{failing_files}\n\n"
    "Error Details:\n{error_details}\n\n"
    "Existing Code:\n{existing_code}\n\n"
    "Provide only the corrected files with complete replacement contents."
)

FINAL_REPORT_PROMPT = (
    "Compile a final software execution summary for:\n\n"
    "Task:\n{task_description}\n\n"
    "Generated Files:\n{generated_files}\n\n"
    "Modified Files:\n{modified_files}\n\n"
    "Execution History:\n{execution_history}\n\n"
    "Test Results:\n{test_results}\n\n"
    "Remaining Errors:\n{error_logs}\n\n"
    "Repair Attempts:\n{repair_attempts}"
)
