from langgraph.graph import StateGraph, END  # core LangGraph building blocks

from app.state import AgentState  # the shared state type
from app.nodes import (  # node functions and the router
    understand_node, classify_node, response_node,
    review_node, fix_node, final_node, route_after_review,
)


def build_graph():  # builds and compiles the workflow
    workflow = StateGraph(AgentState)  # create a graph that uses our state

    workflow.add_node("understand", understand_node)  # register each node under a name
    workflow.add_node("classify", classify_node)  # classify node
    workflow.add_node("response", response_node)  # response node
    workflow.add_node("review", review_node)  # review node
    workflow.add_node("fix", fix_node)  # fix node
    workflow.add_node("final", final_node)  # final node

    workflow.set_entry_point("understand")  # the graph starts here
    workflow.add_edge("understand", "classify")  # understand -> classify
    workflow.add_edge("classify", "response")  # classify -> response
    workflow.add_edge("response", "review")  # response -> review

    workflow.add_conditional_edges(  # branch based on the router's return value
        "review",  # after the review node...
        route_after_review,  # ...run the router function
        {"fix": "fix", "final": "final"},  # map router output to next node
    )

    workflow.add_edge("fix", "review")  # the loop: fix goes back to review
    workflow.add_edge("final", END)  # finish the graph

    return workflow.compile()  # turn the definition into a runnable graph


graph = build_graph()  # compiled graph used by main.py