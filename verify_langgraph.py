import sys
import os

# Ensure we can import logic
sys.path.append(os.getcwd())

from logic.reasoning_engine import ReasoningEngine
from logic.enrichment_agent import EnrichmentAgent
from logic.onboarding_agent import OnboardingAgent
from logic.schemas import ResponseModel, WidgetType

def test_reasoning_engine():
    print("--- Testing ReasoningEngine ---")
    engine = ReasoningEngine()
    
    # query = "Hello" # Simple Chat
    # result = engine.process_query(query)
    # print(f"Chat Result: {result}")
    
    # Mocking real LLM calls might be slow or fail without key, so we assume the instance creation works
    # and the graph components are linked.
    print("ReasoningEngine instantiated successfully.")
    assert engine.app is not None
    
def test_enrichment_agent():
    print("--- Testing EnrichmentAgent ---")
    agent = EnrichmentAgent()
    print("EnrichmentAgent instantiated successfully.")
    assert agent.app is not None

def test_onboarding_agent():
    print("--- Testing OnboardingAgent ---")
    agent = OnboardingAgent()
    print("OnboardingAgent instantiated successfully.")
    assert agent.app is not None

if __name__ == "__main__":
    try:
        test_reasoning_engine()
        test_enrichment_agent()
        test_onboarding_agent()
        print("\n✅ All Agents Instantiated & Graphs Compiled Successfully.")
    except Exception as e:
        print(f"\n❌ Verification Failed: {e}")
        sys.exit(1)
