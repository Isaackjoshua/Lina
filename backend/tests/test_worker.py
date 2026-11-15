from lina.worker.__main__ import build_scheduler


def test_scheduler_runs_in_east_africa_time() -> None:
    scheduler = build_scheduler()
    assert str(scheduler.timezone) == "Africa/Dar_es_Salaam"
    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {"heartbeat", "pipeline"}
    assert "hour='4'" in str(jobs["pipeline"].trigger) and "minute='0'" in str(
        jobs["pipeline"].trigger
    )
