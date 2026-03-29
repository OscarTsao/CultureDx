from pathlib import Path

from omegaconf import OmegaConf

from culturedx.ontology.icd10 import list_disorders

EXPECTED_TARGET_DISORDERS = ["F32", "F33", "F41.1", "F42", "F43.1"]


def test_final_target_disorders_config_matches_ontology() -> None:
    config_path = (
        Path(__file__).resolve().parents[1]
        / "configs"
        / "targets"
        / "final_target_disorders.yaml"
    )
    cfg = OmegaConf.load(str(config_path))
    plain = OmegaConf.to_container(cfg, resolve=True)
    target_disorders = plain.get("target_disorders") if isinstance(plain, dict) else None

    assert target_disorders == EXPECTED_TARGET_DISORDERS

    ontology_disorders = set(list_disorders())
    missing = [code for code in target_disorders if code not in ontology_disorders]
    assert missing == []
