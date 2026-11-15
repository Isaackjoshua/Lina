from lina.worker.__main__ import build_scheduler


def test_scheduler_runs_in_east_africa_time() -> None:
    scheduler = build_scheduler()
    assert str(scheduler.timezone) == "Africa/Dar_es_Salaam"
    assert [job.id for job in scheduler.get_jobs()] == ["heartbeat"]
