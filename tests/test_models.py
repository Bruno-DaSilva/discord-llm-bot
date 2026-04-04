from src.models import CachedCommandData, CachedOutputData, PipelineData


class TestCachedCommandData:
    def test_construct_with_pipeline_and_extra(self):
        pipeline = PipelineData(input="topic", context={"messages": ["msg"]})
        cached = CachedCommandData(
            cmd_type="issue",
            pipeline_data=pipeline,
            extra={"author_username": "alice", "latest_message_link": None},
        )
        assert cached.pipeline_data is pipeline
        assert cached.cmd_type == "issue"
        assert cached.extra["author_username"] == "alice"

    def test_extra_defaults_to_empty_dict(self):
        pipeline = PipelineData(input="topic")
        cached = CachedCommandData(cmd_type="test", pipeline_data=pipeline)
        assert cached.extra == {}


class TestCachedOutputData:
    def test_construct_with_payload(self):
        cached = CachedOutputData(
            cmd_type="issue",
            payload={"title": "Bug", "body": "Details"},
        )
        assert cached.cmd_type == "issue"
        assert cached.payload["title"] == "Bug"

    def test_payload_defaults_to_empty_dict(self):
        cached = CachedOutputData(cmd_type="test")
        assert cached.payload == {}


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
