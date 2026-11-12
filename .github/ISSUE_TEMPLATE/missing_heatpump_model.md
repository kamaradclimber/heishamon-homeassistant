---
name: Missing heat pump model
about: Your heat pump is reported as "Unknown model for HeishaMon"
title: 'Missing heat pump model: '
labels: ''
assignees: ''

---

<!--
👋 Thanks for reporting a missing model. Model definitions are maintained by the HeishaMon project,
not added independently in heishamon-homeassistant.
-->

**Add the model upstream first**

The source of truth is
[HeatPumpType.md](https://github.com/heishamon/HeishaMon/blob/main/HeatPumpType.md)
in the [heishamon/HeishaMon](https://github.com/heishamon/HeishaMon) repository. Please submit a PR there
and wait for it to be merged before reporting the model as missing here. Do not open a PR to add the model
directly to heishamon-homeassistant.

**After the upstream change is merged**

The [weekly sync workflow](https://github.com/kamaradclimber/heishamon-homeassistant/actions/workflows/sync-heatpump-models.yml)
brings upstream model-list changes into heishamon-homeassistant through an automated PR. If you want Home
Assistant to recognize the model before that sync is available, you can refresh it yourself:

1. Open the **HeishaMon** device in Home Assistant.
2. Press **Refresh heat pump models** in the diagnostic section.
3. The model is recognized immediately, without restarting Home Assistant.

If the model is still unknown after refreshing, please report it here and include a link to the merged upstream PR.

**Model details**

<!-- The signature is the 10-byte value reported by TOP92 / Heat_Pump_Model. -->

- Signature (bytes 129 - 138): ....
- Indoor unit (IDU): ....
- Outdoor unit (ODU): ....
- KIT: ....
- Power [kW]: ....
- 1ph/3ph: ....
- T-CAP/HP: ....
