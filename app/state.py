from typing import TypedDict  # TypedDict lets us define the shape of the state dictionary


class AgentState(TypedDict):  # the shared "notebook" every node reads from and writes to
    customer_query: str       # the original customer message
    category: str             # ORDER_STATUS, DAMAGED_PRODUCT, etc.
    priority: str             # LOW, MEDIUM or HIGH
    issue_summary: str        # the Understand node's analysis
    generated_response: str   # the current draft reply (overwritten by the Fix node)
    review_feedback: str      # the reviewer's comments
    approved: bool            # the reviewer's decision, which the router reads
    final_response: str       # the accepted reply
    iteration_count: int      # how many fix cycles have run (the loop limit)