from dotenv import load_dotenv  # loads variables from .env

load_dotenv()  # must run BEFORE importing the graph, so GROQ_API_KEY is available

import json  # for saving the result as JSON
import os  # for creating the output folder

from app.graph import graph  # the compiled LangGraph workflow


def main() -> None:  # program entry point
    print("=" * 40)  # header top line
    print("       AI CUSTOMER SUPPORT AGENT")  # title
    print("=" * 40)  # header bottom line
    query = input("\nEnter customer query:\n\n> ").strip()  # read the customer message
    if not query:  # guard against empty input
        print("No query entered.")  # tell the user
        return  # stop the program

    initial_state = {  # starting state, exactly as in the assignment
        "customer_query": query,  # user input
        "category": "",  # filled by classify
        "priority": "",  # filled by classify
        "issue_summary": "",  # filled by understand
        "generated_response": "",  # filled by response/fix
        "review_feedback": "",  # filled by review
        "approved": False,  # filled by review
        "final_response": "",  # filled by final
        "iteration_count": 0,  # incremented by fix
    }

    try:  # catch unexpected graph errors
        result = graph.invoke(initial_state)  # run the whole workflow
    except Exception as e:  # e.g. bad API key, no internet
        print(f"\nWorkflow failed: {e}")  # show the error
        return  # stop the program

    os.makedirs("output", exist_ok=True)  # create output/ if missing
    with open("output/final_response.txt", "w", encoding="utf-8") as f:  # open the text file
        f.write(result["final_response"])  # save the final reply
    with open("output/execution_result.json", "w", encoding="utf-8") as f:  # open the JSON file
        json.dump(result, f, indent=4, ensure_ascii=False)  # save the full final state
    print("\n\nSaved: output/final_response.txt and output/execution_result.json")  # confirm


if __name__ == "__main__":  # run only when executed directly
    main()  # start the app