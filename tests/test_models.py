from src.models import CachedIssueData, IssueMetadata, PipelineData


class TestIssueMetadata:
    def test_construct_with_all_fields(self):
        meta = IssueMetadata(
            author_username="alice",
            latest_message_link="https://discord.com/channels/1/2/3",
        )
        assert meta.author_username == "alice"
        assert meta.latest_message_link == "https://discord.com/channels/1/2/3"

    def test_link_can_be_none(self):
        meta = IssueMetadata(author_username="bob", latest_message_link=None)
        assert meta.latest_message_link is None


class TestCachedIssueData:
    def test_construct_with_pipeline_and_metadata(self):
        pipeline = PipelineData(input="topic", context={"messages": ["msg"]})
        meta = IssueMetadata(author_username="alice", latest_message_link=None)
        cached = CachedIssueData(pipeline_data=pipeline, metadata=meta)
        assert cached.pipeline_data is pipeline
        assert cached.metadata is meta


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
