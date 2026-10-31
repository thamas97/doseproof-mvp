"""Shared generated-model inputs for integration checks (no captured history)."""
from plant.config import load_baseline
from plant.events import EventFactory, plant_feedback, sensor_observation
from plant.model import PlantModel
from plant.sensors import SensorAdapter


def generated_events(run='generated-integration-test', steps=1):
    b=load_baseline();model=PlantModel(b);factory=EventFactory(run)
    a,sensor_b=SensorAdapter(b.sensor_a),SensorAdapter(b.sensor_b)
    records=[]
    for _ in range(steps):
        state=model.step()
        records.extend([plant_feedback(factory,state),sensor_observation(factory,a.sample(state.modeled_residual_mg_l,state.sim_step)),sensor_observation(factory,sensor_b.sample(state.modeled_residual_mg_l,state.sim_step))])
    return records
