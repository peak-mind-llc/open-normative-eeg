"""Pipeline orchestrator: preprocessing → spectral → connectivity.

Provides process_resting() as the single entry point for running
the full normative EEG analysis pipeline on a resting-state recording,
and MetricsResult for structured access to the outputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from open_normative.parameters import PIPELINE_PARAMS
from open_normative.preprocessing import preprocess
from open_normative.spectral import analyze_spectral
from open_normative.connectivity import analyze_connectivity


@dataclass
class MetricsResult:
    """Structured result from process_resting().

    Fields:
        condition: Recording condition label (e.g. "eo", "ec").
        preprocessing: Output dict from preprocess() — bad_channels, ica, etc.
        spectral: Output dict from analyze_spectral() — band_power, ratios, etc.
        connectivity: Output dict from analyze_connectivity(), or None if skipped.
    """

    condition: str
    preprocessing: dict
    spectral: Optional[dict]
    connectivity: Optional[dict]

    def to_flat_dict(self) -> dict:
        """Flatten spectral band-power metrics into a single dict.

        Keys follow the pattern "<channel>.<band>.<metric>", e.g.:
            "Fz.Alpha.absolute_power"
            "Fz.Alpha.relative_power"
            "Fz.Alpha.corrected_absolute_power"
            "Fz.Alpha.corrected_relative_power"
            "Fz.Alpha.Theta/Beta"  (for ratios stored per-channel)

        Returns:
            Flat dict of metric keys → float values.
        """
        result = {}
        if self.spectral is None:
            return result

        band_power = self.spectral.get("band_power", {})
        corrected_band_power = self.spectral.get("corrected_band_power", {})
        ch_names = self.spectral.get("ch_names", [])
        if not ch_names:
            for bp in band_power.values():
                arr = bp.get("absolute")
                if arr is not None and hasattr(arr, "__len__"):
                    break

        for band, powers in band_power.items():
            abs_arr = powers.get("absolute")
            rel_arr = powers.get("relative")
            if abs_arr is None:
                continue
            for i, ch in enumerate(ch_names):
                result[f"{ch}.{band}.absolute_power"] = float(abs_arr[i])
                if rel_arr is not None:
                    result[f"{ch}.{band}.relative_power"] = float(rel_arr[i])

        # Corrected (specparam) band power
        for band, powers in corrected_band_power.items():
            corr_abs = powers.get("corrected_absolute")
            corr_rel = powers.get("corrected_relative")
            if corr_abs is None:
                continue
            for i, ch in enumerate(ch_names):
                result[f"{ch}.{band}.corrected_absolute_power"] = float(corr_abs[i])
                if corr_rel is not None:
                    result[f"{ch}.{band}.corrected_relative_power"] = float(corr_rel[i])

        # Ratios: {ratio_name: {ch_name: value}}
        for ratio_name, ch_map in self.spectral.get("ratios", {}).items():
            for ch, val in ch_map.items():
                result[f"{ch}.{ratio_name}"] = float(val) if val == val else None

        # Corrected ratios
        for ratio_name, ch_map in self.spectral.get("corrected_ratios", {}).items():
            for ch, val in ch_map.items():
                result[f"{ch}.corrected_{ratio_name}"] = (
                    float(val) if val == val else None
                )

        # Asymmetry indices: {pair_key: {band: value}}
        for pair_key, band_dict in self.spectral.get("asymmetry", {}).items():
            for band, val in band_dict.items():
                result[f"{pair_key}.{band}.asymmetry_index"] = float(val)

        # GSF-corrected band power
        for band, powers in self.spectral.get("gsf_band_power", {}).items():
            gsf_abs = powers.get("gsf_absolute")
            gsf_rel = powers.get("gsf_relative")
            if gsf_abs is None:
                continue
            for i, ch in enumerate(ch_names):
                result[f"{ch}.{band}.gsf_absolute_power"] = float(gsf_abs[i])
                if gsf_rel is not None:
                    result[f"{ch}.{band}.gsf_relative_power"] = float(gsf_rel[i])

        # GSF scalar
        gsf_val = self.spectral.get("gsf")
        if gsf_val is not None:
            result["_subject.broadband.gsf"] = float(gsf_val)

        # IAF (Individual Alpha Frequency)
        iaf = self.spectral.get("iaf", {})
        if iaf:
            if iaf.get("global_peak") is not None:
                result["_subject.broadband.iaf_peak"] = iaf["global_peak"]
            global_cog = iaf.get("global_cog")
            if global_cog is not None and global_cog == global_cog:
                result["_subject.broadband.iaf_cog"] = global_cog
            for ch, ch_iaf in iaf.get("per_channel", {}).items():
                if ch_iaf.get("peak_freq") is not None:
                    result[f"{ch}.broadband.iaf_peak"] = ch_iaf["peak_freq"]
                cog = ch_iaf.get("cog_freq")
                if cog is not None and cog == cog:
                    result[f"{ch}.broadband.iaf_cog"] = cog

        # PAC metrics (from connectivity)
        if self.connectivity is not None:
            pac = self.connectivity.get("pac")
            if pac and "theta_gamma_pac" in pac:
                tg_pac = pac["theta_gamma_pac"]
                for hub, mi in tg_pac.get("within_hub", {}).items():
                    result[f"_hub_{hub}.ThetaGamma.pac_mi"] = float(mi)
                for pair_key, mi in tg_pac.get("between_hub", {}).items():
                    result[f"_pac_{pair_key}.ThetaGamma.pac_mi"] = float(mi)

        return result

    def to_nested_dict(self) -> dict:
        """Return spectral band-power metrics as a nested dict.

        Structure: {channel: {band: {"absolute_power": ..., "relative_power": ...,
                    "corrected_absolute_power": ..., "corrected_relative_power": ...}}}

        This is the format expected by the normative builder and compare module.

        Returns:
            Nested dict.
        """
        result: dict = {}
        if self.spectral is None:
            return result

        band_power = self.spectral.get("band_power", {})
        corrected_band_power = self.spectral.get("corrected_band_power", {})
        ch_names = self.spectral.get("ch_names", [])

        for band, powers in band_power.items():
            abs_arr = powers.get("absolute")
            rel_arr = powers.get("relative")
            if abs_arr is None:
                continue
            for i, ch in enumerate(ch_names):
                if ch not in result:
                    result[ch] = {}
                if band not in result[ch]:
                    result[ch][band] = {}
                result[ch][band]["absolute_power"] = float(abs_arr[i])
                if rel_arr is not None:
                    result[ch][band]["relative_power"] = float(rel_arr[i])

        # Corrected (specparam) band power
        for band, powers in corrected_band_power.items():
            corr_abs = powers.get("corrected_absolute")
            corr_rel = powers.get("corrected_relative")
            if corr_abs is None:
                continue
            for i, ch in enumerate(ch_names):
                if ch not in result:
                    result[ch] = {}
                if band not in result[ch]:
                    result[ch][band] = {}
                result[ch][band]["corrected_absolute_power"] = float(corr_abs[i])
                if corr_rel is not None:
                    result[ch][band]["corrected_relative_power"] = float(corr_rel[i])

        # Ratios: store under each channel with ratio name as band key.
        for ratio_name, ch_map in self.spectral.get("ratios", {}).items():
            for ch, val in ch_map.items():
                if ch not in result:
                    result[ch] = {}
                if ratio_name not in result[ch]:
                    result[ch][ratio_name] = {}
                result[ch][ratio_name]["value"] = (
                    float(val) if val == val else None
                )

        # Corrected ratios
        for ratio_name, ch_map in self.spectral.get("corrected_ratios", {}).items():
            for ch, val in ch_map.items():
                if ch not in result:
                    result[ch] = {}
                corrected_key = f"corrected_{ratio_name}"
                if corrected_key not in result[ch]:
                    result[ch][corrected_key] = {}
                result[ch][corrected_key]["value"] = (
                    float(val) if val == val else None
                )

        # Aperiodic parameters: offset and exponent per channel.
        # Stored under band="broadband" (not band-specific).
        # Only include channels with good aperiodic fit (r_squared >= 0.85).
        aperiodic = self.spectral.get("aperiodic", {})
        for ch, ap in aperiodic.items():
            r_sq = ap.get("r_squared", 0.0)
            fit_quality = ap.get("fit_quality", "skipped")
            if fit_quality != "good" or r_sq < 0.85:
                continue
            offset = ap.get("offset")
            exponent = ap.get("exponent")
            if offset is None or exponent is None:
                continue
            if math.isnan(offset) or math.isnan(exponent):
                continue
            if ch not in result:
                result[ch] = {}
            if "broadband" not in result[ch]:
                result[ch]["broadband"] = {}
            result[ch]["broadband"]["aperiodic_offset"] = float(offset)
            result[ch]["broadband"]["aperiodic_exponent"] = float(exponent)

        # Asymmetry indices: store under pair channel key (e.g. "F3/F4")
        asymmetry = self.spectral.get("asymmetry", {})
        for pair_key, band_dict in asymmetry.items():
            if pair_key not in result:
                result[pair_key] = {}
            for band, value in band_dict.items():
                if band not in result[pair_key]:
                    result[pair_key][band] = {}
                result[pair_key][band]["asymmetry_index"] = float(value)

        # GSF-corrected band power
        for band, powers in self.spectral.get("gsf_band_power", {}).items():
            gsf_abs = powers.get("gsf_absolute")
            gsf_rel = powers.get("gsf_relative")
            if gsf_abs is None:
                continue
            for i, ch in enumerate(ch_names):
                if ch not in result:
                    result[ch] = {}
                if band not in result[ch]:
                    result[ch][band] = {}
                result[ch][band]["gsf_absolute_power"] = float(gsf_abs[i])
                if gsf_rel is not None:
                    result[ch][band]["gsf_relative_power"] = float(gsf_rel[i])

        # GSF scalar: store under _subject channel
        gsf_val = self.spectral.get("gsf")
        if gsf_val is not None:
            if "_subject" not in result:
                result["_subject"] = {}
            if "broadband" not in result["_subject"]:
                result["_subject"]["broadband"] = {}
            result["_subject"]["broadband"]["gsf"] = float(gsf_val)

        # IAF (Individual Alpha Frequency)
        iaf = self.spectral.get("iaf", {})
        if iaf:
            # Global IAF under _subject channel
            if "_subject" not in result:
                result["_subject"] = {}
            if "broadband" not in result["_subject"]:
                result["_subject"]["broadband"] = {}
            if iaf.get("global_peak") is not None:
                result["_subject"]["broadband"]["iaf_peak"] = iaf["global_peak"]
            global_cog = iaf.get("global_cog")
            if global_cog is not None and not (
                isinstance(global_cog, float) and math.isnan(global_cog)
            ):
                result["_subject"]["broadband"]["iaf_cog"] = global_cog

            # Per-channel IAF
            for ch, ch_iaf in iaf.get("per_channel", {}).items():
                if ch not in result:
                    result[ch] = {}
                if "broadband" not in result[ch]:
                    result[ch]["broadband"] = {}
                if ch_iaf.get("peak_freq") is not None:
                    result[ch]["broadband"]["iaf_peak"] = ch_iaf["peak_freq"]
                cog = ch_iaf.get("cog_freq")
                if cog is not None and not (
                    isinstance(cog, float) and math.isnan(cog)
                ):
                    result[ch]["broadband"]["iaf_cog"] = cog

        # Connectivity: dwPLI node strength per electrode per band
        if self.connectivity is not None:
            elec_conn = self.connectivity.get("electrode_connectivity", {})
            node_strength = elec_conn.get("node_strength", {})
            conn_ch_names = elec_conn.get("ch_names", [])

            for method, band_data in node_strength.items():
                metric_name = f"{method}_node_strength"
                for band, values in band_data.items():
                    if values is None:
                        continue
                    for i, ch in enumerate(conn_ch_names):
                        if i >= len(values):
                            break
                        if ch not in result:
                            result[ch] = {}
                        if band not in result[ch]:
                            result[ch][band] = {}
                        val = float(values[i])
                        result[ch][band][metric_name] = val if val == val else None

            # Graph metrics per band (stored under a synthetic "graph" channel)
            graph_metrics = self.connectivity.get("graph_metrics", {})
            if graph_metrics:
                result["_graph"] = {}
                for band, gm in graph_metrics.items():
                    result["_graph"][band] = {
                        "global_efficiency": gm.get("global_efficiency"),
                        "char_path_length": gm.get("char_path_length"),
                    }

            # Hub-level connectivity matrices (store for downstream viz)
            hub_conn = self.connectivity.get("hub_connectivity", {})
            hub_names = self.connectivity.get("hub_names", [])
            if hub_conn and hub_names:
                for method, band_data in hub_conn.items():
                    for band, matrix in band_data.items():
                        if matrix is None:
                            continue
                        metric_name = f"{method}_hub"
                        for i, hub_i in enumerate(hub_names):
                            hub_ch = f"_hub_{hub_i}"
                            if hub_ch not in result:
                                result[hub_ch] = {}
                            if band not in result[hub_ch]:
                                result[hub_ch][band] = {}
                            for j, hub_j in enumerate(hub_names):
                                if i != j:
                                    key = f"{metric_name}_{hub_j}"
                                    result[hub_ch][band][key] = float(matrix[i, j])

            # PAC metrics (theta-gamma phase-amplitude coupling)
            pac = self.connectivity.get("pac")
            if pac and "theta_gamma_pac" in pac:
                tg_pac = pac["theta_gamma_pac"]
                for hub, mi in tg_pac.get("within_hub", {}).items():
                    hub_ch = f"_hub_{hub}"
                    if hub_ch not in result:
                        result[hub_ch] = {}
                    if "ThetaGamma" not in result[hub_ch]:
                        result[hub_ch]["ThetaGamma"] = {}
                    result[hub_ch]["ThetaGamma"]["pac_mi"] = float(mi)

                for pair_key, mi in tg_pac.get("between_hub", {}).items():
                    pac_ch = f"_pac_{pair_key}"
                    if pac_ch not in result:
                        result[pac_ch] = {}
                    if "ThetaGamma" not in result[pac_ch]:
                        result[pac_ch]["ThetaGamma"] = {}
                    result[pac_ch]["ThetaGamma"]["pac_mi"] = float(mi)

        return result


def process_resting(
    raw,
    condition: str,
    params: Optional[dict] = None,
    skip_connectivity: bool = False,
) -> MetricsResult:
    """Run the full resting-state EEG analysis pipeline.

    Orchestrates: copy raw → preprocess → spectral analysis →
    (optional) connectivity analysis → MetricsResult.

    The caller's Raw object is never modified — we work on a copy.

    Args:
        raw: MNE Raw object (19-channel, channel-standardized).
        condition: Recording condition label, e.g. "eo" or "ec".
        params: Pipeline params dict. Defaults to PIPELINE_PARAMS.
        skip_connectivity: If True, skip connectivity analysis (faster,
            useful for large normative builds where connectivity is not needed).

    Returns:
        MetricsResult with preprocessing, spectral, and connectivity fields.
    """
    if params is None:
        params = PIPELINE_PARAMS

    # Work on a copy so the caller's data is untouched.
    raw_copy = raw.copy()

    # Preprocess.
    prep_result = preprocess(raw_copy, params["preprocessing"])
    processed_raw = prep_result["raw"]
    ch_names = list(processed_raw.ch_names)

    # Spectral analysis.
    spectral_result = analyze_spectral(processed_raw, params["spectral"])
    # Attach ch_names so MetricsResult can build flat/nested dicts without
    # needing the Raw object.
    spectral_result["ch_names"] = ch_names

    # Connectivity (optional).
    connectivity_result = None
    if not skip_connectivity:
        connectivity_result = analyze_connectivity(
            processed_raw, params["connectivity"]
        )

    return MetricsResult(
        condition=condition,
        preprocessing={
            "bad_channels": prep_result.get("bad_channels", []),
            "ica": prep_result.get("ica", {}),
        },
        spectral=spectral_result,
        connectivity=connectivity_result,
    )
