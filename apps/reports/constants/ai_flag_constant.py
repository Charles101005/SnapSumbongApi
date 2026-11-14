# Officer decisions on the advisory AI screening flag.
#
# These are NOT report workflow statuses: they answer the "Is this report
# valid?" review question and are recorded in the audit trail. Once a decision
# is made the report/image flags are cleared so the report looks like a normal
# submission again, while the review history stays on the timeline.
AI_FLAG_DECISION_CLEARED = "CLEARED"
AI_FLAG_DECISION_CONFIRMED = "CONFIRMED"
AI_FLAG_DECISIONS = (AI_FLAG_DECISION_CLEARED, AI_FLAG_DECISION_CONFIRMED)
