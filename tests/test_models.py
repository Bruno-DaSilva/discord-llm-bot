from src.models import PipelineData


class TestPipelineData:
    def test_construct_with_context_and_input(self):
        data = PipelineData(
            context={"messages": ["hello", "world"]},
            input="test topic",
        )
        assert data.context == {"messages": ["hello", "world"]}
        assert data.input == "test topic"

    def test_context_defaults_to_empty_dict(self):
        data = PipelineData(input="topic")
        assert data.context == {}

    def test_equality(self):
        a = PipelineData(context={"k": ["v"]}, input="x")
        b = PipelineData(context={"k": ["v"]}, input="x")
        assert a == b

    def test_inequality(self):
        a = PipelineData(context={}, input="x")
        b = PipelineData(context={}, input="y")
        assert a != b
