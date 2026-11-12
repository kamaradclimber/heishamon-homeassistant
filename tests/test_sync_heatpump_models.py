import pytest

from scripts.sync_heatpump_models import parse_heatpump_models, replace_mapping


MARKDOWN = """
| Value | Bytes 129 - 138 | IDU | ODU | KIT | Power [kW] | 1ph/3ph | T-CAP/HP |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | AA 01 02 03 04 05 06 07 08 09 | Monoblock | WH-MDC05H3E5 | Monoblock | 5 | 1ph | HP |
| 1 | BB 01 02 03 04 05 06 07 08 09 | WH-SDC09K3E8 | WH-UDZ09KE8 | KIT-WC09K3E8 | 9 | 3ph | HP |
"""


def test_parse_heatpump_models_uses_first_non_monoblock_name():
    assert parse_heatpump_models(MARKDOWN) == {
        "AA 01 02 03 04 05 06 07 08 09": "WH-MDC05H3E5 5 1ph HP",
        "BB 01 02 03 04 05 06 07 08 09": "WH-SDC09K3E8 9 3ph HP",
    }


def test_parse_heatpump_models_rejects_unexpected_table_format():
    with pytest.raises(ValueError, match="Could not find"):
        parse_heatpump_models("| Name | Model |\n| --- | --- |\n")


def test_parse_heatpump_models_rejects_duplicate_signatures():
    duplicate = MARKDOWN + "| 2 | AA 01 02 03 04 05 06 07 08 09 | Monoblock | WH-MDC07H3E5 | Monoblock | 7 | 1ph | HP |\n"
    with pytest.raises(ValueError, match="Duplicate model signature"):
        parse_heatpump_models(duplicate)


def test_replace_mapping_changes_only_the_generated_mapping():
    source = '''HEATPUMP_MODELS = {"0": "legacy"}\n\nHEATPUMP_MODELS_39 = {\n    "old": "old model",\n}\n'''

    updated = replace_mapping(source, parse_heatpump_models(MARKDOWN))

    assert 'HEATPUMP_MODELS = {"0": "legacy"}' in updated
    assert '"AA 01 02 03 04 05 06 07 08 09": "WH-MDC05H3E5 5 1ph HP"' in updated
    assert '"old": "old model"' not in updated
    assert replace_mapping(updated, parse_heatpump_models(MARKDOWN)) == updated
