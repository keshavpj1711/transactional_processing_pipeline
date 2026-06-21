from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "transactions_sample.csv"


def _upload(client):
    with open(FIXTURE, "rb") as f:
        return client.post(
            "/jobs/upload",
            files={"file": ("transactions_sample.csv", f, "text/csv")},
        )


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_upload_returns_job_id(client):
    resp = _upload(client)
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["status"] in {"pending", "processing", "completed"}


def test_full_flow_upload_status_results(client):
    job_id = _upload(client).json()["job_id"]

    status = client.get(f"/jobs/{job_id}/status").json()
    assert status["status"] == "completed"
    assert status["summary"]["row_count_raw"] == 95
    assert status["summary"]["row_count_clean"] == 85

    results = client.get(f"/jobs/{job_id}/results").json()
    assert len(results["transactions"]) == 85
    assert len(results["anomalies"]) >= 1
    assert results["category_breakdown"]
    assert results["summary"]["narrative"]


def test_list_jobs_and_status_filter(client):
    _upload(client)
    assert len(client.get("/jobs").json()) == 1
    assert len(client.get("/jobs?status=completed").json()) == 1
    assert client.get("/jobs?status=pending").json() == []


def test_invalid_status_filter_rejected(client):
    assert client.get("/jobs?status=bogus").status_code == 422


def test_non_csv_rejected(client):
    resp = client.post(
        "/jobs/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 422


def test_missing_columns_rejected(client):
    resp = client.post(
        "/jobs/upload",
        files={"file": ("bad.csv", b"a,b,c\n1,2,3\n", "text/csv")},
    )
    assert resp.status_code == 422


def test_unknown_job_returns_404(client):
    assert client.get("/jobs/9999/status").status_code == 404
    assert client.get("/jobs/9999/results").status_code == 404
