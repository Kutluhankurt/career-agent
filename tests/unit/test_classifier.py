from career.ai.base import AIError, FakeProvider, strict_schema
from career.analysis.analyzer import analyze
from career.analysis.classifier import ActivityAnalysis, classify_rules, validate_ai
from career.analysis.confidence import band, word
from career.analysis.context import ContextPacket, GitCommitContext, GitContext


def ctx(**kw) -> ContextPacket:
    base = dict(session_id="s1", date="2026-10-16", time="09:12-10:04", active_minutes=52,
                applications={"VS Code": 25, "Chrome": 12, "Terminal": 9, "Excel": 6}, window_titles=[],
                sites=["Jira"], workspaces=["supervisor"], files=["temperature_test.py", "Temperature_Result.xlsx", "config.yaml"],
                commands=["pytest"], tickets=["AI-1842"],
                git=[GitContext(repository="supervisor", commits=[GitCommitContext(hash="abc123", message="Fix temperature validation")])])
    base.update(kw)
    return ContextPacket(**base)


def test_rules_supervisor_testing():
    a = classify_rules(ctx(), project="Supervisor")
    assert a.category == "Testing"
    assert a.activity == "Supervisor testing"
    assert {"Python", "pytest", "Test automation", "Excel", "Jira", "Git"} <= set(a.skills)
    assert {"AI-1842", "temperature_test.py", "pytest", "abc123"} <= set(a.evidence)
    assert 0.8 <= a.confidence <= 0.9


def test_rules_categories():
    assert classify_rules(ctx(applications={"Slack": 30, "Outlook": 10}, files=[], commands=[], tickets=[], sites=[], git=[],
                              workspaces=[])).category == "Communication"
    assert classify_rules(ctx(files=["version_updater.py"], commands=[], tickets=[], sites=[])).category == "Development"
    investigation = classify_rules(ctx(applications={"Chrome": 30}, files=[], commands=[], git=[], workspaces=[]))
    assert investigation.category == "Investigation" and "Debugging" in investigation.skills
    assert classify_rules(ctx(applications={"Terminal": 20}, files=["device_0412.tm"], commands=[], git=[], tickets=[], sites=[])).category == "Analysis"
    other = classify_rules(ctx(applications={"Spotify": 20}, files=[], commands=[], git=[], tickets=[], sites=[], workspaces=[]))
    assert other.category == "Other" and other.confidence <= 0.5


def test_ai_output_is_validated_against_context():
    raw = ActivityAnalysis(activity="Improved reliability by 37% in Supervisor testing", category="testing", confidence=0.99,
                           skills=["Python", "python", "Leadership of the whole company team"], evidence=["AI-1842", "secret.py", "PYTEST"])
    v = validate_ai(raw, ctx(), "Supervisor")
    assert v.category == "Testing"
    assert "37%" not in v.activity
    assert v.evidence == ["AI-1842", "pytest"]      # invented file dropped, case restored
    assert v.skills == ["Python"]                   # duplicates and nonsense removed
    assert v.confidence == 0.97                     # never "certain"
    weak = validate_ai(raw.model_copy(update={"evidence": ["nothing.txt"]}), ctx(), None)
    assert weak.confidence <= 0.5


def test_analyzer_uses_rules_when_confident_or_offline():
    p = FakeProvider([{"activity": "x" * 5, "category": "Testing", "confidence": 0.9, "skills": [], "evidence": [], "project": None}])
    _, by, _ = analyze(ctx(), "Supervisor", p)
    assert by == "rules" and p.calls == []           # rules were sure enough
    _, by, _ = analyze(ctx(), "Supervisor", FakeProvider(up=False), deep=True)
    assert by == "rules"


def test_analyzer_asks_ai_when_unsure_and_merges_observed_skills():
    thin = ctx(sites=[], commands=[], tickets=[], git=[], files=["notes.md"], applications={"VS Code": 10})
    p = FakeProvider([{"activity": "Supervisor documentation", "project": None, "category": "Documentation", "confidence": 0.85,
                       "skills": ["Technical writing"], "evidence": ["notes.md", "made-up.pdf"]}])
    result, by, model = analyze(thin, "Supervisor", p)
    assert (by, model) == ("fake", "fake-1")
    assert result.activity == "Supervisor documentation"
    assert result.evidence == ["notes.md"]
    assert result.project == "Supervisor"
    assert '"workspaces":["supervisor"]' in p.calls[0][1]


def test_analyzer_retries_invalid_output_once_then_falls_back():
    thin = ctx(sites=[], commands=[], tickets=[], git=[], files=[], applications={"VS Code": 10})
    p = FakeProvider(["not json", '{"activity": "ok"}'])
    result, by, _ = analyze(thin, None, p)
    assert by == "rules" and len(p.calls) == 2
    p = FakeProvider([AIError("offline")])
    _, by, _ = analyze(thin, None, p)
    assert by == "rules" and len(p.calls) == 1      # network errors aren't retried


def test_strict_schema_shape():
    schema = strict_schema(ActivityAnalysis)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"activity", "project", "category", "confidence", "skills", "evidence"}
    assert schema["properties"]["project"]["type"] == ["string", "null"]
    assert "maxLength" not in str(schema)


def test_confidence_words():
    assert [band(x) for x in (0.2, 0.5, 0.7, 0.9, 0.97)] == ["Unknown", "Weak", "Possible", "Strong", "Very strong"]
    assert [word(x) for x in (0.5, 0.65, 0.86, 0.95)] == ["Unsure", "Possibly", "Likely", "Very likely"]
