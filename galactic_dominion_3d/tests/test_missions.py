import random

from game.missions.mission import (FAILED, SUCCESS, MissionRuntime, WaveDirector, apply_rewards, complete_mission,
                                   kill_rewards, mission_rewards)


def mission(config, mission_id):
    return config.mission(mission_id)


def test_destroy_count_filters_by_enemy(config):
    _, m = mission(config, "iron_stations")
    run = MissionRuntime(m)
    run.on_enemy_killed("fighter")
    assert run.kills == 0
    run.on_enemy_killed("sentinel_station")
    run.on_enemy_killed("sentinel_station")
    assert run.state == SUCCESS


def test_survive_timer(config):
    _, m = mission(config, "crimson_ambush")
    run = MissionRuntime(m)
    run.update(m["params"]["duration"] - 1)
    assert run.state != SUCCESS
    run.update(2)
    assert run.state == SUCCESS


def test_defend_fails_when_station_destroyed(config):
    _, m = mission(config, "orion_defend")
    run = MissionRuntime(m)
    run.on_ally_destroyed("Orión-7")
    assert run.state == FAILED and "Orión-7" in run.fail_reason


def test_elite_mission_needs_elite_kill(config):
    _, m = mission(config, "crimson_elite")
    run = MissionRuntime(m)
    run.on_enemy_killed("interceptor", elite=False)
    assert run.state != SUCCESS
    run.on_enemy_killed("interceptor", elite=True)
    assert run.state == SUCCESS


def test_wave_director_spawns_reinforcements_when_few_alive():
    director = WaveDirector([{"delay": 0, "enemies": {"scout": 3}}, {"delay": 1, "enemies": {"fighter": 2}}],
                            reinforce_at=1)
    first = director.update(0.1, alive=0)
    assert first == [{"type": "scout", "count": 3, "elite": False}]
    assert director.update(5, alive=3) == []          # todavía quedan muchos
    assert director.update(0.5, alive=1) == []        # empieza la cuenta atrás de 1 s
    assert director.update(0.6, alive=1)[0]["type"] == "fighter"
    assert director.all_spawned


def test_looping_waves_never_run_out():
    director = WaveDirector([{"delay": 0, "enemies": {"scout": 1}}], reinforce_at=0, loop=True)
    for _ in range(5):
        assert director.update(0.1, alive=0)
    assert not director.all_spawned


def test_boss_rewards_include_blueprint_once(config):
    galaxy, m = mission(config, "orion_boss")
    rng = random.Random(1)
    first = mission_rewards(galaxy, m, rng, config, first_time=True)
    again = mission_rewards(galaxy, m, rng, config, first_time=False)
    assert "scatter_gun" in first["blueprints"] and first["items"]
    assert not again["blueprints"] and again["credits"] < first["credits"]


def test_completing_main_missions_unlocks_next_galaxy(profile, config):
    galaxy = config.galaxy("orion")
    for m in galaxy["missions"]:
        if m["main"]:
            events = complete_mission(profile, galaxy, m, config)
    assert events["galaxy_unlocked"] == "crimson"
    assert "crimson" in profile.unlocked_galaxies
    assert profile.flags["workshop_unlocked"]


def test_final_boss_completes_campaign(profile, config):
    galaxy = config.galaxy("void")
    events = {}
    for m in galaxy["missions"]:
        events = complete_mission(profile, galaxy, m, config)
    assert events["campaign_complete"]


def test_kill_rewards_scale_with_galaxy_and_elite(config):
    rng = random.Random(4)
    scout = config.enemies["scout"]
    normal = kill_rewards(scout, config.galaxy("orion"), False, rng, config)
    hard = kill_rewards(scout, config.galaxy("void"), True, rng, config)
    assert hard["xp"] > normal["xp"] and hard["credits"] > normal["credits"]


def test_apply_rewards(profile, config):
    rewards = {"xp": 10_000, "credits": 500, "materials": {"alloy": 5}, "blueprints": ["plasma_cannon"], "items": []}
    before = profile.credits
    result = apply_rewards(profile, rewards, config)
    assert profile.credits == before + 500
    assert "plasma_cannon" in profile.blueprints
    assert result["levels"] and profile.level > 1
