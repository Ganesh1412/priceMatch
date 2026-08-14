from pathlib import Path
from xml.etree import ElementTree


BPMN_PATH = Path(__file__).parent.parent / "camunda" / "price-match-agent-pipeline.bpmn"
BPMN_NAMESPACE = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"
BPMN_DI_NAMESPACE = "{http://www.omg.org/spec/BPMN/20100524/DI}"
ZEEBE_NAMESPACE = "{http://camunda.org/schema/zeebe/1.0}"


def test_agent_pipeline_has_a_worker_task_for_each_agent():
    root = ElementTree.parse(BPMN_PATH).getroot()
    job_types = {
        task.find(f".//{ZEEBE_NAMESPACE}taskDefinition").attrib["type"]
        for task in root.findall(f".//{BPMN_NAMESPACE}serviceTask")
    }

    assert job_types == {
        "price-match.researcher",
        "price-match.solution-designer",
        "price-match.prototyper",
        "price-match.communicator",
        "price-match.manager",
    }


def test_agent_pipeline_requires_human_review_for_confirmed_matches():
    root = ElementTree.parse(BPMN_PATH).getroot()
    gateway = root.find(f".//{BPMN_NAMESPACE}exclusiveGateway[@id='review_gate']")
    review_flow = root.find(f".//{BPMN_NAMESPACE}sequenceFlow[@id='flow_confirmed_to_human_review']")
    condition = review_flow.find(f"{BPMN_NAMESPACE}conditionExpression")

    assert gateway is not None
    assert gateway.attrib["default"] == "flow_hold_for_validation"
    assert condition is not None
    assert "proceed_with_conditions" in condition.text
    assert "confirmed" in condition.text


def test_agent_pipeline_includes_a_diagram_for_the_agent_handoffs():
    root = ElementTree.parse(BPMN_PATH).getroot()
    diagram = root.find(f"{BPMN_DI_NAMESPACE}BPMNDiagram")
    diagrammed_elements = {
        shape.attrib["bpmnElement"]
        for shape in root.findall(f".//{BPMN_DI_NAMESPACE}BPMNShape")
    }

    assert diagram is not None
    assert {"researcher", "solution_designer", "prototyper", "communicator", "manager", "review_gate"} <= diagrammed_elements