# Standard Library
import time
from uuid import uuid4

# Third Party
import pytest
import vcr

# DocumentCloud
from documentcloud.client import DocumentCloud
from documentcloud.exceptions import DoesNotExistError

# Test against a development environment documentcloud instance
BASE_URI = "http://api.dev.documentcloud.org/api/"
AUTH_URI = "http://dev.squarelet.com/api/"
USERNAME = "test-user"
PASSWORD = "test-password"
TIMEOUT = 1.0
DEFAULT_DOCUMENT_URI = "https://assets.documentcloud.org/documents/20071460/test.pdf"


# We want to enable VCR for all tests
def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.vcr(match_on=["method", "uri", "body", "headers"]))


@pytest.fixture(scope="session")
@vcr.use_cassette("tests/cassettes/fixtures/client.yaml")
def client():
    return DocumentCloud(
        username=USERNAME,
        password=PASSWORD,
        base_uri=BASE_URI,
        auth_uri=AUTH_URI,
        timeout=TIMEOUT,
    )


@pytest.fixture
def public_client():
    return DocumentCloud(base_uri=BASE_URI, auth_uri=AUTH_URI, timeout=TIMEOUT)


def _wait_document(document, client, record_mode):
    # wait for document to finish processing
    while document.status in ("nofile", "pending"):
        if record_mode == "all":
            time.sleep(1)
        document = client.documents.get(document.id)
    assert document.status == "success"
    return document


@pytest.fixture(scope="session")
@vcr.use_cassette("tests/cassettes/fixtures/document.yaml")
def document(project, client, record_mode):
    document = client.documents.upload(
        DEFAULT_DOCUMENT_URI,
        access="private",
        data={"_tag": ["document"]},
        description="A simple test document",
        source="DocumentCloud",
        related_article="https://www.example.com/article/",
        published_url="https://www.example.com/article/test.pdf",
        projects=[project.id],
    )
    document = _wait_document(document, client, record_mode)
    yield document
    document.delete()


@pytest.fixture(scope="session")
def document_factory(client, record_mode):
    documents = []

    def make_document(pdf=DEFAULT_DOCUMENT_URI, **kwargs):
        document = client.documents.upload(pdf, **kwargs)
        document = _wait_document(document, client, record_mode)
        documents.append(document)
        return document

    yield make_document

    for document in documents:
        try:
            document.delete()
        except DoesNotExistError:
            # test deleted the document
            pass


@pytest.fixture(scope="session")
@vcr.use_cassette("tests/cassettes/fixtures/project.yaml")
def project(client, document_factory):
    document = document_factory()
    title = f"This is a project for testing {uuid4()}"
    project = client.projects.create(
        title, "This is a project for testing", document_ids=[document.id]
    )
    yield project
    project.delete()


@pytest.fixture(scope="session")
def project_factory(client, record_mode):
    projects = []

    def make_project(title="Project Factory", *args, **kwargs):

        project = client.projects.create(title, *args, **kwargs)
        projects.append(project)
        return project

    yield make_project

    for project in projects:
        try:
            project.delete()
        except DoesNotExistError:
            # test deleted the project
            pass
