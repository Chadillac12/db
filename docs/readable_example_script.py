"""
OOP/readability rewrite of `example_script.py` that preserves behavior.

Changes vs. the legacy script:
- Introduces `RunConfig`, `RunContext`, and `Harness` to make lifecycle and
  signal operations easier to read and safer while keeping call order intact.
- Wraps requirements into classes (`Requirement2A`, `Requirement2B`) but keeps
  the exact signal values, sleeps, logging, and test case numbering.
- Keeps the import-time mocks so the file can still be imported on machines
  without proprietary `utilities` / `test_initialization` packages.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass  # @dataclass generates init/eq/repr; frozen=True makes it immutable.
from contextlib import contextmanager  # @contextmanager turns a generator into a with-statement helper.
from typing import Dict, Any
from unittest.mock import Mock


# Template/script metadata mirrors the original
_template_revision_ = '$Revision: v05 $'
_module_revision_ = r'''
$CC_VERSION$  \main\13
'''


# --- Imports & mocking (kept to mirror original behavior) --------------------
# NOTE: These mocks mask missing proprietary packages at import time. That is
# exactly what the original file did. We keep it for fidelity, even though
# fail-fast imports are usually safer in production.
sys.modules['utilities'] = Mock()
sys.modules['test_initialization'] = Mock()

import utilities as u
import test_initialization


# Immutable config bag; keeps all toggles in one place.
@dataclass(frozen=True)
class RunConfig:
    program: str = 'CACTCS'
    author: str = 'Name'
    current_rcn: str = 'RCN SRSA-17'

    record_data: bool = True
    pwr_start_stop: bool = True

    rec_id_2a: str = 's3_2_2_1_3_1_2_2__2a'
    rec_id_2b: str = 's3_2_2_1_3_1_2_2__2b'
    rec_freq_hz: int = 32


class Harness:
    """Tiny wrapper around utilities to shrink repetition."""

    def set_many(self, pairs: Dict[str, Any]) -> None:
        for sig, val in pairs.items():
            u.SetSignal(sig, val)

    def check_many(self, pairs: Dict[str, Any]) -> None:
        for sig, val in pairs.items():
            u.CheckSignal(sig, val)

    def settle(self, seconds: float = 1.0) -> None:
        u.sleep(seconds)


class RunContext:
    """Owns script lifecycle: rig on/off, logging, init, recording."""

    def __init__(self, config: RunConfig, script_name: str):
        self.config = config
        self.script_name = script_name
        self.h = Harness()

    @contextmanager
    def script_scope(self):
        started_rig = False
        log_open = False
        try:
            if self.config.pwr_start_stop:
                u.init_module.start_rig()
                started_rig = True

            u.OpenLogFile(self.script_name)
            log_open = True
            yield
        finally:
            if log_open:
                try:
                    u.CloseLogFile()
                except Exception:
                    pass
            if started_rig:
                try:
                    u.down_module.stop_rig()
                except Exception:
                    pass

    @contextmanager
    def recording(self, rec_id: str):
        if not self.config.record_data:
            yield
            return
        u.StartRecording(rec_id, screen_name=rec_id, rec_freq_hz=self.config.rec_freq_hz)
        try:
            yield
        finally:
            u.StopRecording()

    def log_script_header(self) -> None:
        u.GatherScriptInfo(self.config.program, self.config.author, self.config.current_rcn, _template_revision_)
        u.WriteToLog(u.AssembleLogheader())

    def initialize(self) -> None:
        test_initialization.standard_init()

    def report_errors(self) -> None:
        u.ErrorCount()


class Requirement2A:
    """Requirement 2a: validity flag and data parameter logic (behavior preserved)."""

    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.h = ctx.h

    def run(self) -> None:
        testcase = 0
        UUT_list = ['lctc1']
        aircraft_type_list = ['passenger', 'freighter']
        testpoint = 1
        input_parameter_validity_table = [
            ('flight_phase_lss_v', 'flight_phase_lss', 1, 'flight_phase_lss_v_oc',
             'flight_phase_lss_oc', 'flight_phase_data_def', 'flight_phase_v',
             'flight_phase', 'l_409_w03_p_raw', 'flight_phase_p_v',
             'flight_phase_s_v', 3, 1, 7, 'flight_number_p1_data_def'),
            ('baro_altitude_lss_v', 'baro_altitude_lss', 0.01, 'baro_altitude_lss_v_oc',
             'baro_altitude_lss_oc', 'baro_altitude_data_def', 'baro_altitude_v',
             'baro_altitude', 'l_70a_w04_p_raw', 'baro_altitude_p_v',
             'baro_altitude_s_v', 121, 512, 22, 'baro_altitude_lss_data_def'),
            ('gnd_speed_lss_v', 'gnd_speed_lss', 0.125, 'gnd_speed_lss_v_oc',
             'gnd_speed_lss_oc', 'gnd_speed_data_def', 'gnd_speed_v',
             'gnd_speed', 'l_eae_w11_p_raw', 'gnd_speed_p_v',
             'gnd_speed_s_v', 13, 128, 0, 'gnd_speed_lss_data_def'),
            ('equip_cool_sw_lss_v', 'equip_cool_sw_lss', 1/64, 'equip_cool_sw_lss_v_oc',
             'equip_cool_sw_lss_oc', 'equip_cool_sw_def', 'equip_cool_sw_v',
             'equip_cool_sw', 'l_e77_w03_p_raw', 'equip_cool_and_voc_p_v',
             'equip_cool_and_voc_s_v', 3, 64, 2, 'equip_cool_sw_lss_def'),
            ('gnd_test_data_load_sw_lss_v', 'gnd_test_data_load_sw_lss', 1/256,
             'gnd_test_data_load_sw_lss_v_oc', 'gnd_test_data_load_sw_lss_oc',
             'gnd_test_data_load_sw_def', 'gnd_test_data_load_sw_v',
             'gnd_test_data_load_sw', 'l_ea4_w02_p_raw', 'gnd_test_data_load_p_v',
             'gnd_test_data_load_s_v', 1, 1024, 2, 'gnd_test_data_load_sw_lss_def'),
            ('engine_run_lss_v', 'engine_run_lss', 1/2048,
             'engine_run_lss_v_oc', 'engine_run_lss_oc',
             'engine_run_data_def', 'engine_run_v', 'engine_run',
             'l_eb0_w10_p_raw', 'engine_running_l_p_v', 'engine_running_l_s_v',
             1, 2048, 0, 'engine_idle_l_def'),
            ('total_air_temp_lss_v', 'total_air_temp_lss', 0.125,
             'total_air_temp_lss_v_oc', 'total_air_temp_lss_oc',
             'total_air_temp_data_def', 'total_air_temp_v', 'total_air_temp',
             'l_fed_w07_p_raw', 'total_air_temp_p_v', 'total_air_temp_s_v',
             -15.0, 1024, -100.0, 'total_air_temp_lss_data_def'),
            ('flow_priority_sw_lss_v', 'flow_priority_sw_lss', 2/512,
             'flow_priority_sw_lss_v_oc', 'flow_priority_sw_lss_oc',
             'flow_priority_sw_def', 'flow_priority_sw_v', 'flow_priority_sw',
             'l_e77_w03_p_raw', 'equip_cool_and_voc_p_v', 'equip_cool_and_voc_s_v',
             0, 512, 0, 'flow_priority_sw_lss_def')
        ]

        for aircraft_type_signal in aircraft_type_list:
            for uut_base in UUT_list:
                testcase = self._run_for_channel(
                    uut_base,
                    aircraft_type_signal,
                    input_parameter_validity_table,
                    testpoint,
                    testcase,
                )

    def _run_for_channel(self, uut_base: str, aircraft_type_signal: str, table, testpoint: int, testcase: int) -> int:
        uut = f"{uut_base}::"
        # Small helper closes over prefix so signal names stay consistent.
        def s(name: str) -> str:
            return f"{uut}{name}"

        # Local testcase counter so numbering stays explicit and less error-prone.
        case_no = testcase

        def next_case(case_type: str = 'normal') -> int:
            """Increment and register the next testcase number with the harness."""
            nonlocal case_no
            case_no += 1
            u.SetTestCase(testpoint, case_no, type=case_type)
            return case_no
        u.WriteToLog('#-- Req 2a Test start for channel: ' + uut + ' for ' + aircraft_type_signal + '--#', color='green')
        u.WriteToLog('Building the signals')

        k_css_no_info_time = s('k_css_no_info_time')
        k_disable_all_label_aquisition_inputs = s('k_disable_all_label_aquisition_inputs')
        k_disable_all_can_inputs = s('k_disable_all_can_inputs')
        aircraft_type = s('aircraft_type')

        if aircraft_type_signal == 'freighter':
            u.SetSignal(aircraft_type, 8)
            u.sleep(1)
            u.CheckSignal(aircraft_type, 8)
        else:
            u.SetSignal(aircraft_type, 7)
            u.sleep(1)
            u.CheckSignal(aircraft_type, 7)

        u.SetSignal(k_disable_all_label_aquisition_inputs, 1)
        u.SetSignal(k_disable_all_can_inputs, 1)
        u.sleep(1)
        u.CheckSignal(k_disable_all_label_aquisition_inputs, 1)
        u.CheckSignal(k_disable_all_can_inputs, 1)

        u.CheckSignal(k_css_no_info_time, 5)

        for (validity1, parameter1, resolution, validity2, parameter2,
             defaultflag, opV, opP, inputdata, primV, secV, lesstol,
             set_value1, initial_value, defaultflagloc) in table:

            validity_local = s(validity1)
            parameter_local = s(parameter1)
            validity_oth = s(validity2)
            parameter_oth = s(parameter2)
            default_flag = s(defaultflag)
            output_V = s(opV)
            output_P = s(opP)
            ctc_input_data = s(inputdata)
            primary_V = s(primV)
            secondary_V = s(secV)
            default_flag_loc = s(defaultflagloc)

            u.WriteToLog('---- Requirement 2a is Started----', color='green')
            if opP == 'flight_phase':
                u.WriteToLog('---- For Parameter Flight_Phase ----', color='orange')
            elif opP == 'baro_altitude':
                u.WriteToLog('---- For Parameter Baro_Altitude ----', color='orange')
            elif opP == 'gnd_speed':
                u.WriteToLog('---- For Parameter Gnd_Speed ----', color='orange')
            elif opP == 'equip_cool_sw':
                u.WriteToLog('---- For Parameter Equip_Cool_Sw ----', color='orange')
            elif opP == 'gnd_test_data_load_sw':
                u.WriteToLog('---- For Parameter Gnd_Test_Data_Load_Sw ----', color='orange')
            elif opP == 'engine_run':
                u.WriteToLog('---- For Parameter Engine_Run ----', color='orange')
            elif opP == 'total_air_temp':
                u.WriteToLog('---- For Parameter Total_Air_Temp ----', color='orange')
            else:
                u.WriteToLog('---- For Parameter Flow_Priority_Sw ----', color='orange')

            u.WriteToLog('---- Check outputs are set to different value before checking their initial Test case value ----', color='green')
            u.SetSignal(default_flag, 0)
            u.SetSignal(primary_V, 0)
            u.SetSignal(secondary_V, 0)
            u.SetSignal(ctc_input_data, set_value1)
            u.SetSignal(validity_oth, 1)
            u.SetSignal(parameter_oth, lesstol)
            u.sleep(1)
            u.CheckSignal(validity_local, 0)

            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, lesstol)
            u.SetSignal(primary_V, 0)
            u.SetSignal(validity_oth, 0)
            u.sleep(1)
            u.CheckSignal(primary_V, 0)
            u.CheckSignal(validity_oth, 0)
            u.CheckSignal(validity_local, 0)

            u.CheckSignal(output_V, 0)
            u.CheckSignal(output_P, lesstol)
            u.CheckSignal(default_flag, 0)

            next_case('normal')

            u.WriteToLog(' ---- Setting the Test Condition for Verification case a ----', color='green')

            u.SetSignal(primary_V, 1)
            u.SetSignal(secondary_V, 0)
            u.SetSignal(ctc_input_data, set_value1)
            u.SetSignal(validity_oth, 0)
            u.SetSignal(parameter_oth, lesstol)
            u.sleep(1)
            if resolution == 0.125 and initial_value == -100.0:
                expected_output = (64 * resolution * 1.8) + 32.0
            elif resolution == 0.01:
                expected_output = 64 * resolution
            else:
                expected_output = set_value1 * resolution

            u.WriteToLog(' ---- Verifying the Test Condition for Verification case a ----', color='green')
            u.CheckSignal(parameter_local, expected_output)
            u.CheckSignal(default_flag, 0)
            u.CheckSignal(validity_local, 1)
            u.CheckSignal(validity_oth, 0)
            u.CheckSignal(parameter_oth, lesstol)
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.WriteToLog(' ---- Verifying the Output Signals for Verification case a ----', color='green')
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, expected_output)

            next_case('normal')
            u.WriteToLog(' ---- Setting the Test Condition for Verification case b ----', color='green')
            u.SetSignal(primary_V, 0)
            u.SetSignal(validity_oth, 1)
            u.SetSignal(parameter_oth, lesstol)
            u.sleep(1)

            u.WriteToLog(' ---- Verifying the Test Condition for Verification case b ----', color='green')
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(parameter_local, expected_output)
            u.CheckSignal(parameter_oth, lesstol)
            u.CheckSignal(default_flag, 0)
            u.CheckSignal(validity_local, 0)
            u.CheckSignal(validity_oth, 1)

            u.WriteToLog(' ---- Verifying the Output Signals for Verification case b ----', color='green')
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, lesstol)

            u.SetSignal(default_flag_loc, 0)
            u.SetSignal(primary_V, 0)
            u.SetSignal(validity_oth, 0)
            u.sleep(6)
            u.CheckSignal(output_V, 0)
            u.CheckSignal(output_P, initial_value)

            next_case('normal')
            u.WriteToLog(' ---- Setting the Test Condition for Verification case e ----', color='green')
            u.SetSignal(default_flag_loc, 0)
            u.SetSignal(primary_V, 1)
            u.SetSignal(validity_oth, 0)
            u.SetSignal(parameter_oth, lesstol)
            u.sleep(4)

            u.WriteToLog(' ---- Verifying the Test Condition for Verification case e ----', color='green')
            u.CheckSignal(default_flag, 1)
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, initial_value)
            u.sleep(2)
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(parameter_local, expected_output)
            u.CheckSignal(primary_V, 1)
            u.CheckSignal(ctc_input_data, set_value1)
            u.CheckSignal(validity_local, 1)
            u.CheckSignal(validity_oth, 0)
            u.CheckSignal(parameter_oth, lesstol)
            u.WriteToLog(' ---- Verifying the Output Signals for Verification case e ----', color='green')
            u.PostProcess('Manually verify output_V, output_P and default_flag when validity_local is True for K_CSS_No_Info_Time seconds in csv record file s3_2_2_1_3_1_2_2__2a')
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, expected_output)
            u.CheckSignal(default_flag, 0)

            next_case('normal')
            u.WriteToLog(' ---- Setting the Test Condition for Verification case c and d ----', color='green')
            u.SetSignal(primary_V, 0)
            u.SetSignal(validity_oth, 0)
            u.sleep(4)

            u.WriteToLog(' ---- Verifying the Test Condition for Verification case c ----', color='green')
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(validity_oth, 0)
            u.CheckSignal(default_flag, 0)
            u.CheckSignal(validity_local, 0)

            u.WriteToLog(' ---- Verifying the Output Signals for Verification case c ----', color='green')
            u.CheckSignal(output_V, 0)
            u.CheckSignal(output_P, expected_output)

            u.WriteToLog(' ---- Verifying the Test Condition for Verification case d ----', color='green')
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(validity_oth, 0)
            u.CheckSignal(default_flag, 0)
            u.CheckSignal(validity_local, 0)
            u.sleep(2)
            u.WriteToLog(' ---- Verifying the Output Signals for Verification case d ----', color='green')
            u.PostProcess('Manually verify output_V, output_P and default_flag when validity_oth and validity_local are False for K_CSS_No_Info_Time seconds in csv record file s3_2_2_1_3_1_2_2__2a')
            u.CheckSignal(output_V, 0)
            u.CheckSignal(output_P, initial_value)
            u.CheckSignal(default_flag, 1)

            next_case('normal')
            u.WriteToLog(' ---- Setting the Test Condition for Verification case f ----', color='green')
            u.SetSignal(default_flag_loc, 0)
            u.SetSignal(validity_oth, 1)
            u.SetSignal(primary_V, 0)
            u.SetSignal(parameter_oth, lesstol)
            u.sleep(4)

            u.WriteToLog(' ---- Verifying the Test Condition for Verification case f ----', color='green')
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(validity_oth, 1)
            u.CheckSignal(default_flag, 1)
            u.CheckSignal(validity_local, 0)
            u.CheckSignal(parameter_oth, lesstol)

            u.WriteToLog(' ---- Verifying the Output Signals for Verification case f ----', color='green')
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, initial_value)
            u.CheckSignal(default_flag, 1)
            u.sleep(2)
            u.PostProcess('Manually verify output_V, output_P and default_flag when validity_oth is True and validity_local is False for K_CSS_No_Info_Time seconds in csv record file s3_2_2_1_3_1_2_2__2a')
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, lesstol)
            u.CheckSignal(default_flag, 0)

            u.SetSignal(k_css_no_info_time, 3)
            u.SetSignal(default_flag_loc, 0)
            u.SetSignal(primary_V, 0)
            u.SetSignal(validity_oth, 0)
            u.sleep(4)
            u.CheckSignal(output_V, 0)
            u.CheckSignal(output_P, initial_value)

            next_case('robust')
            u.WriteToLog(' ---- Setting the Test Condition for Verification case g ----', color='green')
            u.SetSignal(default_flag_loc, 0)
            u.SetSignal(validity_oth, 1)
            u.SetSignal(primary_V, 0)
            u.SetSignal(parameter_oth, lesstol)
            u.sleep(2)

            u.WriteToLog(' ---- Verifying the Test Condition for Verification case g ----', color='green')
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(k_css_no_info_time, 3)
            u.CheckSignal(validity_oth, 1)
            u.CheckSignal(default_flag, 1)
            u.CheckSignal(validity_local, 0)
            u.CheckSignal(parameter_oth, lesstol)

            u.WriteToLog(' ---- Verifying the Output Signals for Verification case g ----', color='green')
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, initial_value)
            u.CheckSignal(default_flag, 1)
            u.sleep(2)
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, lesstol)
            u.CheckSignal(default_flag, 0)

            u.SetSignal(k_css_no_info_time, 5)
            u.sleep(1)
            u.CheckSignal(k_css_no_info_time, 5)

            next_case('normal')
            u.WriteToLog(' ---- Setting the Test Condition for Verification case h ----', color='green')
            u.SetSignal(default_flag_loc, 0)
            u.SetSignal(primary_V, 1)
            u.SetSignal(validity_oth, 1)
            u.SetSignal(parameter_oth, lesstol)
            u.sleep(1)

            u.WriteToLog(' ---- Verifying the Test Condition for Verification case h ----', color='green')
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(parameter_local, expected_output)
            u.CheckSignal(default_flag, 0)
            u.CheckSignal(validity_local, 1)
            u.CheckSignal(validity_oth, 1)
            u.CheckSignal(parameter_oth, lesstol)

            u.WriteToLog(' ---- Verifying the Output Signals for Verification case h ----', color='green')
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, expected_output)

            u.SetSignal(default_flag_loc, 0)
            u.SetSignal(primary_V, 0)
            u.SetSignal(validity_oth, 0)
            u.sleep(6)
            u.CheckSignal(output_V, 0)
            u.CheckSignal(output_P, initial_value)

            next_case('normal')
            u.WriteToLog(' ---- Setting the Test Condition for Verification case i ----', color='green')
            u.SetSignal(default_flag_loc, 0)
            u.SetSignal(primary_V, 1)
            u.SetSignal(validity_oth, 1)
            u.SetSignal(parameter_oth, lesstol)
            u.sleep(4)

            u.WriteToLog(' ---- Verifying the Test Condition for Verification case i ----', color='green')
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(default_flag, 1)
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, initial_value)
            u.sleep(2)
            u.CheckSignal(parameter_local, expected_output)
            u.CheckSignal(primary_V, 1)
            u.CheckSignal(ctc_input_data, set_value1)
            u.CheckSignal(validity_local, 1)
            u.CheckSignal(validity_oth, 1)
            u.CheckSignal(parameter_oth, lesstol)
            u.WriteToLog(' ---- Verifying the Output Signals for Verification case i ----', color='green')
            u.CheckSignal(output_V, 1)
            u.CheckSignal(output_P, expected_output)
            u.CheckSignal(default_flag, 0)

            u.WriteToLog('---- Requirement 2a is complete----', color='green')
            if opP == 'flight_phase':
                u.WriteToLog('---- For Parameter Flight_Phase ----', color='orange')
            elif opP == 'baro_altitude':
                u.WriteToLog('---- For Parameter Baro_Altitude ----', color='orange')
            elif opP == 'gnd_speed':
                u.WriteToLog('---- For Parameter Gnd_Speed ----', color='orange')
            elif opP == 'equip_cool_sw':
                u.WriteToLog('---- For Parameter Equip_Cool_Sw ----', color='orange')
            elif opP == 'gnd_test_data_load_sw':
                u.WriteToLog('---- For Parameter Gnd_Test_Data_Load_Sw ----', color='orange')
            elif opP == 'engine_run':
                u.WriteToLog('---- For Parameter Engine_Run ----', color='orange')
            else:
                u.WriteToLog('---- For Parameter Total_Air_Temp ----', color='orange')

        u.SetSignal(k_disable_all_label_aquisition_inputs, 0)
        u.SetSignal(k_disable_all_can_inputs, 0)
        u.sleep(1)
        u.CheckSignal(k_disable_all_label_aquisition_inputs, 0)
        u.CheckSignal(k_disable_all_can_inputs, 0)
        return case_no


class Requirement2B:
    """Requirement 2b: test data flag logic (not invoked by default)."""

    def __init__(self, ctx: RunContext):
        self.ctx = ctx
        self.h = ctx.h

    def run(self) -> None:
        UUT_list = ['lctc1', 'lctc2', 'rctc1', 'rctc2']
        aircraft_type_list = ['passenger', 'freighter']
        testpoint = 2
        testcase = 0

        if self.ctx.config.record_data:
            u.StartRecording(self.ctx.config.rec_id_2b, screen_name=self.ctx.config.rec_id_2b, rec_freq_hz=self.ctx.config.rec_freq_hz)

        for aircraft_type_signal in aircraft_type_list:
            for uut_base in UUT_list:
                testcase = self._run_for_channel(uut_base, aircraft_type_signal, testpoint, testcase)

        if self.ctx.config.record_data:
            u.StopRecording()

        u.WriteToLog('--- The 2b requirement is complete---', color='orange')

    def _run_for_channel(self, uut_base: str, aircraft_type_signal: str, testpoint: int, testcase: int) -> int:
        uut = f"{uut_base}::"
        # Shared signal-name helper for this channel.
        def s(name: str) -> str:
            return f"{uut}{name}"

        case_no = testcase

        def next_case(case_type: str = 'normal') -> int:
            """Increment and register the next testcase number with the harness."""
            nonlocal case_no
            case_no += 1
            u.SetTestCase(testpoint, case_no, type=case_type)
            return case_no
        u.WriteToLog('#-- Req 2b Test start for channel: ' + uut_base + ' for ' + aircraft_type_signal + '--#', color='green')

        controller_side = s('controller_side')
        channel_number = s('channel_number')
        fd_sw_app_l_test_data = s('fd_sw_app_l_test_data')
        fd_sw_app_r_test_data = s('fd_sw_app_r_test_data')
        eicas_l_test_data = s('eicas_l_test_data')
        eicas_r_test_data = s('eicas_r_test_data')
        adiru_l_test_data = s('adiru_l_test_data')
        adiru_r_test_data = s('adiru_r_test_data')
        gnd_test_sw_app_l_test_data = s('gnd_test_sw_app_l_test_data')
        gnd_test_sw_app_r_test_data = s('gnd_test_sw_app_r_test_data')
        fd_sw_app_lss_test_data = s('fd_sw_app_lss_test_data')
        fd_sw_app_lss_test_data_oc = s('fd_sw_app_lss_test_data_oc')
        eicas_lss_test_data = s('eicas_lss_test_data')
        eicas_lss_test_data_oc = s('eicas_lss_test_data_oc')
        adiru_lss_test_data = s('adiru_lss_test_data')
        adiru_lss_test_data_oc = s('adiru_lss_test_data_oc')
        gnd_test_sw_app_lss_test_data = s('gnd_test_sw_app_lss_test_data')
        gnd_test_sw_app_lss_test_data_oc = s('gnd_test_sw_app_lss_test_data_oc')
        fd_sw_app_p_test_data = s('fd_sw_app_p_test_data')
        eicas_p_test_data = s('eicas_p_test_data')
        adiru_p_test_data = s('adiru_p_test_data')
        gnd_test_sw_app_p_test_data = s('gnd_test_sw_app_p_test_data')
        adiru_r_test_data = s('adiru_r_test_data')
        k_disable_all_label_aquisition_inputs = s('k_disable_all_label_aquisition_inputs')
        k_disable_all_can_inputs = s('k_disable_all_can_inputs')
        aircraft_type = s('aircraft_type')

        if aircraft_type_signal == 'freighter':
            u.SetSignal(aircraft_type, 8)
            u.sleep(1)
            u.CheckSignal(aircraft_type, 8)
        else:
            u.SetSignal(aircraft_type, 7)
            u.sleep(1)
            u.CheckSignal(aircraft_type, 7)

        u.WriteToLog('--- Setting Disable Flags ----')
        u.SetSignal(k_disable_all_label_aquisition_inputs, 1)
        u.SetSignal(k_disable_all_can_inputs, 1)
        u.sleep(1)
        u.CheckSignal(k_disable_all_label_aquisition_inputs, 1)
        u.CheckSignal(k_disable_all_can_inputs, 1)

        u.WriteToLog('---- Check outputs are set to different value before checking their initial Test case value ----', color='green')
        u.SetSignal(fd_sw_app_p_test_data, 0)
        u.SetSignal(eicas_p_test_data, 0)
        u.SetSignal(adiru_p_test_data, 0)
        u.SetSignal(gnd_test_sw_app_p_test_data, 0)
        u.SetSignal(fd_sw_app_lss_test_data_oc, 1)
        u.SetSignal(eicas_lss_test_data_oc, 1)
        u.SetSignal(adiru_lss_test_data_oc, 1)
        u.SetSignal(gnd_test_sw_app_lss_test_data_oc, 1)
        u.sleep(1)

        if uut == 'lctc1::' or uut == 'rctc2::':
            u.CheckSignal(fd_sw_app_l_test_data, 0)
            u.CheckSignal(fd_sw_app_r_test_data, 1)
            u.CheckSignal(eicas_l_test_data, 0)
            u.CheckSignal(eicas_r_test_data, 1)
            u.CheckSignal(adiru_l_test_data, 0)
            u.CheckSignal(adiru_r_test_data, 1)
            u.CheckSignal(gnd_test_sw_app_l_test_data, 0)
            u.CheckSignal(gnd_test_sw_app_r_test_data, 1)
        else:
            u.CheckSignal(fd_sw_app_l_test_data, 1)
            u.CheckSignal(fd_sw_app_r_test_data, 0)
            u.CheckSignal(eicas_l_test_data, 1)
            u.CheckSignal(eicas_r_test_data, 0)
            u.CheckSignal(adiru_l_test_data, 1)
            u.CheckSignal(adiru_r_test_data, 0)
            u.CheckSignal(gnd_test_sw_app_l_test_data, 1)
            u.CheckSignal(gnd_test_sw_app_r_test_data, 0)

        next_case('normal')

        if uut == 'lctc1::' or uut == 'rctc2::':
            if uut == 'lctc1::':
                u.WriteToLog('--Set the Test Condition for Verification Case a', color='orange')
            else:
                u.WriteToLog('--Set the Test Condition for Verification Case d', color='orange')
            u.SetSignal(fd_sw_app_p_test_data, 1)
            u.SetSignal(eicas_p_test_data, 1)
            u.SetSignal(adiru_p_test_data, 1)
            u.SetSignal(gnd_test_sw_app_p_test_data, 1)
            u.SetSignal(fd_sw_app_lss_test_data_oc, 0)
            u.SetSignal(eicas_lss_test_data_oc, 0)
            u.SetSignal(adiru_lss_test_data_oc, 0)
            u.SetSignal(gnd_test_sw_app_lss_test_data_oc, 0)
            u.sleep(1)

            if uut == 'rctc2::':
                u.WriteToLog('--Verify the Test Condition for Verification Case d', color='orange')
                u.CheckSignal(controller_side, 2)
                u.CheckSignal(channel_number, 2)
            else:
                u.WriteToLog('--Verify the Test Condition for Verification Case a', color='orange')
                u.CheckSignal(controller_side, 1)
                u.CheckSignal(channel_number, 1)
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(fd_sw_app_lss_test_data, 1)
            u.CheckSignal(fd_sw_app_lss_test_data_oc, 0)
            u.CheckSignal(eicas_lss_test_data, 1)
            u.CheckSignal(eicas_lss_test_data_oc, 0)
            u.CheckSignal(adiru_lss_test_data, 1)
            u.CheckSignal(adiru_lss_test_data_oc, 0)
            u.CheckSignal(gnd_test_sw_app_lss_test_data, 1)
            u.CheckSignal(gnd_test_sw_app_lss_test_data_oc, 0)

            if uut == 'rctc2::':
                u.WriteToLog('--Verify the Test Outputs for Verification Case d', color='orange')
                u.CheckSignal(controller_side, 2)
                u.CheckSignal(channel_number, 2)
            else:
                u.WriteToLog('--Verify the Test Outputs for Verification Case a', color='orange')
                u.CheckSignal(controller_side, 1)
                u.CheckSignal(channel_number, 1)
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(fd_sw_app_l_test_data, 1)
            u.CheckSignal(fd_sw_app_r_test_data, 0)
            u.CheckSignal(eicas_l_test_data, 1)
            u.CheckSignal(eicas_r_test_data, 0)
            u.CheckSignal(adiru_l_test_data, 1)
            u.CheckSignal(adiru_r_test_data, 0)
            u.CheckSignal(gnd_test_sw_app_l_test_data, 1)
            u.CheckSignal(gnd_test_sw_app_r_test_data, 0)

            if uut == 'lctc1::':
                u.WriteToLog('--Set the Test Condition for Verification Case a', color='orange')
            else:
                u.WriteToLog('--Set the Test Condition for Verification Case d', color='orange')
            u.SetSignal(fd_sw_app_p_test_data, 0)
            u.SetSignal(eicas_p_test_data, 0)
            u.SetSignal(adiru_p_test_data, 0)
            u.SetSignal(gnd_test_sw_app_p_test_data, 0)
            u.SetSignal(fd_sw_app_lss_test_data_oc, 1)
            u.SetSignal(eicas_lss_test_data_oc, 1)
            u.SetSignal(adiru_lss_test_data_oc, 1)
            u.SetSignal(gnd_test_sw_app_lss_test_data_oc, 1)
            u.sleep(1)

            if uut == 'rctc2::':
                u.WriteToLog('--Verify the Test Condition for Verification Case d', color='orange')
                u.CheckSignal(controller_side, 2)
                u.CheckSignal(channel_number, 2)
            else:
                u.WriteToLog('--Verify the Test Condition for Verification Case a', color='orange')
                u.CheckSignal(controller_side, 1)
                u.CheckSignal(channel_number, 1)
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(fd_sw_app_lss_test_data, 0)
            u.CheckSignal(fd_sw_app_lss_test_data_oc, 1)
            u.CheckSignal(eicas_lss_test_data, 0)
            u.CheckSignal(eicas_lss_test_data_oc, 1)
            u.CheckSignal(adiru_lss_test_data, 0)
            u.CheckSignal(adiru_lss_test_data_oc, 1)
            u.CheckSignal(gnd_test_sw_app_lss_test_data, 0)
            u.CheckSignal(gnd_test_sw_app_lss_test_data_oc, 1)

            if uut == 'rctc2::':
                u.WriteToLog('--Verify the Test Outputs for Verification Case d', color='orange')
                u.CheckSignal(controller_side, 2)
                u.CheckSignal(channel_number, 2)
            else:
                u.WriteToLog('--Verify the Test Outputs for Verification Case a', color='orange')
                u.CheckSignal(controller_side, 1)
                u.CheckSignal(channel_number, 1)
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(fd_sw_app_l_test_data, 0)
            u.CheckSignal(fd_sw_app_r_test_data, 1)
            u.CheckSignal(eicas_l_test_data, 0)
            u.CheckSignal(eicas_r_test_data, 1)
            u.CheckSignal(adiru_l_test_data, 0)
            u.CheckSignal(adiru_r_test_data, 1)
            u.CheckSignal(gnd_test_sw_app_l_test_data, 0)
            u.CheckSignal(gnd_test_sw_app_r_test_data, 1)

        elif uut == 'lctc2::' or uut == 'rctc1::':
            if uut == 'lctc2::':
                u.WriteToLog('--Set the Test Condition for Verification Case b', color='orange')
            else:
                u.WriteToLog('--Set the Test Condition for Verification Case c', color='orange')
            u.SetSignal(fd_sw_app_p_test_data, 1)
            u.SetSignal(eicas_p_test_data, 1)
            u.SetSignal(adiru_p_test_data, 1)
            u.SetSignal(gnd_test_sw_app_p_test_data, 1)
            u.SetSignal(fd_sw_app_lss_test_data_oc, 0)
            u.SetSignal(eicas_lss_test_data_oc, 0)
            u.SetSignal(adiru_lss_test_data_oc, 0)
            u.SetSignal(gnd_test_sw_app_lss_test_data_oc, 0)
            u.sleep(1)

            if uut == 'rctc1::':
                u.WriteToLog('--Verify the Test Condition for Verification Case c', color='orange')
                u.CheckSignal(controller_side, 2)
                u.CheckSignal(channel_number, 1)
            else:
                u.WriteToLog('--Verify the Test Condition for Verification Case b', color='orange')
                u.CheckSignal(controller_side, 1)
                u.CheckSignal(channel_number, 2)
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(fd_sw_app_lss_test_data, 1)
            u.CheckSignal(fd_sw_app_lss_test_data_oc, 0)
            u.CheckSignal(eicas_lss_test_data, 1)
            u.CheckSignal(eicas_lss_test_data_oc, 0)
            u.CheckSignal(adiru_lss_test_data, 1)
            u.CheckSignal(adiru_lss_test_data_oc, 0)
            u.CheckSignal(gnd_test_sw_app_lss_test_data, 1)
            u.CheckSignal(gnd_test_sw_app_lss_test_data_oc, 0)

            if uut == 'rctc1::':
                u.WriteToLog('--Verify the Test Outputs for Verification Case c', color='orange')
                u.CheckSignal(controller_side, 2)
                u.CheckSignal(channel_number, 1)
            else:
                u.WriteToLog('--Verify the Test Outputs for Verification Case b', color='orange')
                u.CheckSignal(controller_side, 1)
                u.CheckSignal(channel_number, 2)
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(fd_sw_app_l_test_data, 0)
            u.CheckSignal(fd_sw_app_r_test_data, 1)
            u.CheckSignal(eicas_l_test_data, 0)
            u.CheckSignal(eicas_r_test_data, 1)
            u.CheckSignal(adiru_l_test_data, 0)
            u.CheckSignal(adiru_r_test_data, 1)
            u.CheckSignal(gnd_test_sw_app_l_test_data, 0)
            u.CheckSignal(gnd_test_sw_app_r_test_data, 1)

            if uut == 'lctc2::':
                u.WriteToLog('--Set the Test Condition for Verification Case b', color='orange')
            else:
                u.WriteToLog('--Set the Test Condition for Verification Case c', color='orange')
            u.SetSignal(fd_sw_app_p_test_data, 0)
            u.SetSignal(eicas_p_test_data, 0)
            u.SetSignal(adiru_p_test_data, 0)
            u.SetSignal(gnd_test_sw_app_p_test_data, 0)
            u.SetSignal(fd_sw_app_lss_test_data_oc, 1)
            u.SetSignal(eicas_lss_test_data_oc, 1)
            u.SetSignal(adiru_lss_test_data_oc, 1)
            u.SetSignal(gnd_test_sw_app_lss_test_data_oc, 1)
            u.sleep(1)

            if uut == 'rctc1::':
                u.WriteToLog('--Verify the Test Conditions for Verification Case c', color='orange')
                u.CheckSignal(controller_side, 2)
                u.CheckSignal(channel_number, 1)
            else:
                u.WriteToLog('--Verify the Test Conditions for Verification Case b', color='orange')
                u.CheckSignal(controller_side, 1)
                u.CheckSignal(channel_number, 2)
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(fd_sw_app_lss_test_data, 0)
            u.CheckSignal(fd_sw_app_lss_test_data_oc, 1)
            u.CheckSignal(eicas_lss_test_data, 0)
            u.CheckSignal(eicas_lss_test_data_oc, 1)
            u.CheckSignal(adiru_lss_test_data, 0)
            u.CheckSignal(adiru_lss_test_data_oc, 1)
            u.CheckSignal(gnd_test_sw_app_lss_test_data, 0)
            u.CheckSignal(gnd_test_sw_app_lss_test_data_oc, 1)

            if uut == 'rctc1::':
                u.WriteToLog('--Verify the Test Outputs for Verification Case c', color='orange')
                u.CheckSignal(controller_side, 2)
                u.CheckSignal(channel_number, 1)
            else:
                u.WriteToLog('--Verify the Test Outputs for Verification Case b', color='orange')
                u.CheckSignal(controller_side, 1)
                u.CheckSignal(channel_number, 2)
            if aircraft_type_signal == 'freighter':
                u.CheckSignal(aircraft_type, 8)
            else:
                u.CheckSignal(aircraft_type, 7)
            u.CheckSignal(fd_sw_app_l_test_data, 1)
            u.CheckSignal(fd_sw_app_r_test_data, 0)
            u.CheckSignal(eicas_l_test_data, 1)
            u.CheckSignal(eicas_r_test_data, 0)
            u.CheckSignal(adiru_l_test_data, 1)
            u.CheckSignal(adiru_r_test_data, 0)
            u.CheckSignal(gnd_test_sw_app_l_test_data, 1)
            u.CheckSignal(gnd_test_sw_app_r_test_data, 0)

        u.WriteToLog('--- Clearing Disable Flags ----')
        u.SetSignal(k_disable_all_label_aquisition_inputs, 0)
        u.SetSignal(k_disable_all_can_inputs, 0)
        u.sleep(1)
        u.CheckSignal(k_disable_all_label_aquisition_inputs, 0)
        u.CheckSignal(k_disable_all_can_inputs, 0)
        return case_no


class ScriptRunner:
    """Coordinates lifecycle + requirements using the OOP helpers."""

    def __init__(self, config: RunConfig):
        self.config = config
        self.script_name = u.GetScriptName(__file__)
        self.ctx = RunContext(config, self.script_name)

    def run(self) -> None:
        with self.ctx.script_scope():
            self.ctx.log_script_header()
            self.ctx.initialize()

            with self.ctx.recording(self.config.rec_id_2a):
                Requirement2A(self.ctx).run()

            # Requirement 2b remains intentionally disabled, matching the legacy script.
            # Requirement2B(self.ctx).run()

            self.ctx.report_errors()
            self.ctx.initialize()


def main() -> None:
    config = RunConfig()
    ScriptRunner(config).run()


if __name__ == '__main__':
    main()
