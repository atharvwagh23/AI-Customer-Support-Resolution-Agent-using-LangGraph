from typing import Literal  # restricts a field to a fixed set of allowed values

from langchain_core.prompts import ChatPromptTemplate  # turns prompt strings into fillable templates
from langchain_groq import ChatGroq  # LangChain wrapper for the Groq LLM
from pydantic import BaseModel, Field  # defines the shape of structured LLM output

from app.prompts import (  # import the 5 prompts
    UNDERSTAND_PROMPT,  # prompt for the understand node
    CLASSIFY_PROMPT,  # prompt for the classify node
    RESPONSE_PROMPT,  # prompt for the response node
    REVIEW_PROMPT,  # prompt for the review node
    FIX_PROMPT,  # prompt for the fix node
)
from app.state import AgentState  # the shared state type

MAX_ITERATIONS = 2  # maximum number of review/fix cycles allowed

# One shared LLM. temperature=0 keeps answers stable and repeatable.
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)  # reads GROQ_API_KEY from the environment


class ClassificationOutput(BaseModel):  # schema for the classify node's structured output
    category: Literal[  # only these seven values are accepted
        "ORDER_STATUS", "DAMAGED_PRODUCT", "WRONG_PRODUCT",
        "REFUND", "PAYMENT", "CANCELLATION", "OTHER",
    ] = Field(description="Ticket category")  # help text sent to the LLM
    priority: Literal["LOW", "MEDIUM", "HIGH"] = Field(description="Ticket priority")  # three valid priorities


class ReviewOutput(BaseModel):  # schema for the reviewer's structured output
    approved: bool = Field(description="True only if all 5 criteria pass")  # real boolean the router can trust
    feedback: str = Field(description="Short feedback, one or two sentences")  # explanation of the decision


def banner(title: str) -> None:  # prints a section header like the assignment example
    print("\n" + "=" * 40)  # top line
    print(title)  # section title
    print("=" * 40 + "\n")  # bottom line


def understand_node(state: AgentState) -> dict:  # NODE 1: analyse the customer message
    banner("UNDERSTANDING CUSTOMER QUERY")  # show progress
    chain = ChatPromptTemplate.from_template(UNDERSTAND_PROMPT) | llm  # prompt -> LLM pipeline
    try:  # protect against API errors
        summary = chain.invoke({"customer_query": state["customer_query"]}).content.strip()  # run the LLM
    except Exception as e:  # if the call fails
        summary = f"Customer Issue: {state['customer_query']} (analysis failed: {e})"  # fall back to raw query
    print(summary)  # show the analysis
    return {"issue_summary": summary}  # write it into the state


def classify_node(state: AgentState) -> dict:  # NODE 2: category + priority (structured output)
    banner("CLASSIFICATION")  # show progress
    structured_llm = llm.with_structured_output(ClassificationOutput)  # force output into our schema
    chain = ChatPromptTemplate.from_template(CLASSIFY_PROMPT) | structured_llm  # prompt -> structured LLM
    try:  # protect against API or parsing errors
        result = chain.invoke({  # fill the prompt placeholders
            "customer_query": state["customer_query"],  # original message
            "issue_summary": state["issue_summary"],  # output of the previous node
        })
        category, priority = result.category, result.priority  # read the validated fields
    except Exception as e:  # if anything fails
        print(f"Classification failed ({e}), using safe defaults.")  # tell the user
        category, priority = "OTHER", "MEDIUM"  # safe fallback values
    print(f"Category:\n{category}\n\nPriority:\n{priority}")  # show the result
    return {"category": category, "priority": priority}  # write both into the state


def response_node(state: AgentState) -> dict:  # NODE 3: draft the first reply
    banner("GENERATING RESPONSE")  # show progress
    chain = ChatPromptTemplate.from_template(RESPONSE_PROMPT) | llm  # prompt -> LLM
    try:  # protect against API errors
        draft = chain.invoke({  # fill the prompt placeholders
            "customer_query": state["customer_query"],  # original message
            "category": state["category"],  # from classify node
            "priority": state["priority"],  # from classify node
            "issue_summary": state["issue_summary"],  # from understand node
        }).content.strip()  # take the text of the reply
    except Exception as e:  # if the call fails
        draft = "Thank you for contacting us. Please share your order number and a description of the problem so our team can review it."  # generic safe reply
        print(f"Response generation failed ({e}), using a generic reply.")  # tell the user
    print(draft)  # show the draft
    return {"generated_response": draft}  # write the draft into the state


def review_node(state: AgentState) -> dict:  # NODE 4: quality check (structured output)
    banner("REVIEW")  # show progress
    structured_llm = llm.with_structured_output(ReviewOutput)  # force output into approved + feedback
    chain = ChatPromptTemplate.from_template(REVIEW_PROMPT) | structured_llm  # prompt -> structured LLM
    try:  # protect against API or parsing errors
        result = chain.invoke({  # fill the prompt placeholders
            "customer_query": state["customer_query"],  # original message
            "category": state["category"],  # ticket category
            "generated_response": state["generated_response"],  # the draft being reviewed
        })
        approved, feedback = result.approved, result.feedback  # read the validated fields
    except Exception as e:  # if the review fails
        approved, feedback = False, f"Review failed ({e}); please recheck the reply."  # not approved; loop limit still protects us
    print(f"Approved:\n{approved}\n\nFeedback:\n{feedback}")  # show the decision
    return {"approved": approved, "review_feedback": feedback}  # write both into the state


def fix_node(state: AgentState) -> dict:  # NODE 5: improve the draft using reviewer feedback
    banner("FIX")  # show progress
    print("Improving response...")  # status message
    chain = ChatPromptTemplate.from_template(FIX_PROMPT) | llm  # prompt -> LLM
    try:  # protect against API errors
        improved = chain.invoke({  # fill the prompt placeholders
            "customer_query": state["customer_query"],  # original message
            "category": state["category"],  # ticket category
            "priority": state["priority"],  # ticket priority
            "generated_response": state["generated_response"],  # current draft
            "review_feedback": state["review_feedback"],  # what needs fixing
        }).content.strip()  # take the text of the reply
    except Exception as e:  # if the call fails
        improved = state["generated_response"]  # keep the current draft
        print(f"Fix failed ({e}), keeping the current draft.")  # tell the user
    return {  # update the state
        "generated_response": improved,  # overwrite the draft with the improved one
        "iteration_count": state["iteration_count"] + 1,  # count this fix cycle
    }


def final_node(state: AgentState) -> dict:  # NODE 6: accept the current draft as the final reply
    banner("FINAL RESPONSE")  # show progress
    if not state["approved"]:  # we got here because the limit was hit
        print("(Maximum iterations reached, latest draft sent for human review.)\n")  # explain why
    print(state["generated_response"])  # show the final reply
    return {"final_response": state["generated_response"]}  # write it into the state


def route_after_review(state: AgentState) -> str:  # CONDITIONAL ROUTER: decides the next node
    if state["approved"]:  # reviewer is happy
        return "final"  # go to final response
    if state["iteration_count"] >= MAX_ITERATIONS:  # out of fix cycles
        return "final"  # stop looping and finish
    return "fix"  # otherwise improve the draft