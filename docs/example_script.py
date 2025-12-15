Apple this prompt to this file - =
# Template script version
_template_revision_ = '$Revision: v05 $'
import sys
from unittest.mock import Mock
sys.modules['utilities'] = Mock()
sys.modules['test_initialization'] = Mock()
# Utilities
import utilities as u

# Initialization Script
import test_initialization

# Get script name (without extension)
script_name = u.GetScriptName(__file__)

# Script Info/Options
program = 'CACTCS'
author = 'Name'
current_rcn = 'RCN SRSA-17'
record_data = True
pwr_start_stop = True
_module_revision_ = r'''
$CC_VERSION$  \main\13
'''

def run_script():
    # Turn on power supplies and start rig
    # **** DTS ONLY
    if pwr_start_stop:
        u.init_module.start_rig()

    # Open Logfile as 'script_name'.LOG
    u.OpenLogFile(script_name)

    # Populate Log Header
    u.GatherScriptInfo(program, author, current_rcn, _template_revision_)
    log_header = u.AssembleLogheader()
    u.WriteToLog(log_header)

    # Run Initialization Script
    test_initialization.standard_init()

    # Test Individual Requirements

    if record_data:
        u.StartRecording('s3_2_2_1_3_1_2_2__2a',\
                            screen_name='s3_2_2_1_3_1_2_2__2a', rec_freq_hz=32)
    reqt_2a_passenger_freighter()
    if record_data:
        u.StopRecording()
    # reqt_2b_passenger_freighter()

    # Report Error Count
    u.ErrorCount()

    # Rerun Initialization Script
    test_initialization.standard_init()

    # Clean up before closing output files
    u.CloseLogFile()

    # Stop rig after script is done
    # **** DTS ONLY
    if pwr_start_stop:
        u.down_module.stop_rig()


# define test procedures


def reqt_2a_passenger_freighter():
    '''
    ---------------------------------------------------------------
    Requirement: 2a) Validity flag and data parameter logic

    Verification Cases:

    a) Set Local Channel Input Validity to True
           Other Channel Input Validity to False
           Default Flag to False
           Local Channel Input Parameter Flag to expected_output
           Other Channel Input Parameter Flag to lesstol

       Output Validity is equal to Local Channel Input Validity
       Output Parameter is equal to Local Channel Input Parameter

    b) Set Local Channel Input Validity to False
           Other Channel Input Validity to True
           Default Flag to False
           Local Channel Input Parameter Flag to expected_output
           Other Channel Input Parameter Flag to lesstol

       Output Validity is equal to Other Channel Input Validity
       Output Parameter is equal to Other Channel Input Parameter

    c) Set Local Channel Input Validity to False and
          Other Channel Input Validity to False for less than K_CSS_No_Info_Time
          Default Flag to False

       Output Validity is equal to False
       Output Parameter is equal to Last Value

    d) Set Local Channel Input Validity to False and
          Other Channel Input Validity to False for greater than or equal to
            K_CSS_No_Info_Time
          Default Flag to False

       Output Validity is equal to False
       Output Parameter is equal to Default Value per Table 3.2.2.1.3.1.2.2-1
       Default Flag = true

    e) Set Local Channel Input Validity to True for greater than or equal to
            K_CSS_No_Info_Time
           Other Channel Input Validity to False
           Local Channel Input Parameter Flag to expected_output
           Other Channel Input Parameter Flag to lesstol
           Default Flag to True

       Output Validity is equal to Local Channel Input Validity
       Output Parameter is equal to Local Channel Input Parameter
       Default Flag is equal to False

    f) Set Local Channel Input Validity to False and
           other Channel Input Validity to True for greater than or equal to
            K_CSS_No_Info_Time
           Other Channel Input Parameter Flag to lesstol
           Default Flag to True

       Output Validity is equal to other Channel Input Validity
       Output Parameter is equal to other Channel Input Parameter
       Default Flag is equal to False

    g) Trim K_CSS_No_Info_Time to 3
        Set Local Channel Input Validity to False and
           other Channel Input Validity to True for greater than or equal to
            K_CSS_No_Info_Time
           Other Channel Input Parameter Flag to lesstol
           Default Flag to True

       Output Validity is equal to other Channel Input Validity
       Output Parameter is equal to other Channel Input Parameter
       Default Flag is equal to False

    h) Set Local Channel Input Validity to True
           Other Channel Input Validity to True
           Default Flag to False
           Local Channel Input Parameter Flag to expected_output
           Other Channel Input Parameter Flag to lesstol

       Output Validity is equal to Local Channel Input Validity
       Output Parameter is equal to Local Channel Input Parameter

    i) Set Local Channel Input Validity to True for greater than or equal to
            K_CSS_No_Info_Time
           Other Channel Input Validity to True
           Local Channel Input Parameter Flag to expected_output
           Other Channel Input Parameter Flag to lesstol
           Default Flag to True

       Output Validity is equal to Local Channel Input Validity
       Output Parameter is equal to Local Channel Input Parameter
       Default Flag is equal to False

    ----------------------------------------------------------------
    script markers:
      test point  - 1       (requirement 2a)
      card type -   lctc1
      Test Case   - 1     (Verification Case a)------------------|
      Test Case   - 2     (Verification Case b)                  |
      Test Case   - 3     (Verification Case e)                  |For
      Test Case   - 4     (Verification Case c & d)              |parameter
      Test Case   - 5     (Verification Case f)                  |flight_phase
      Test Case   - 6     (Verification Case g)**Robust Case     |
      Test Case   - 7     (Verification Case h)                  |
      Test Case   - 8     (Verification Case i)------------------|

      Test Case   - 9     (Verification Case a)------------------|
      Test Case   - 10    (Verification Case b)                  |
      Test Case   - 11    (Verification Case e)                  |For
      Test Case   - 12    (Verification Case c & d)              |parameter
      Test Case   - 13    (Verification Case f)                  |baro_altitude
      Test Case   - 14    (Verification Case g)**Robust Case     |
      Test Case   - 15    (Verification Case h)                  |
      Test Case   - 16    (Verification Case i)------------------|

      Test Case   - 17    (Verification Case a)------------------|
      Test Case   - 18    (Verification Case b)                  |
      Test Case   - 19    (Verification Case e)                  |For
      Test Case   - 20    (Verification Case c & d)              |parameter
      Test Case   - 21    (Verification Case f)                  |gnd_speed
      Test Case   - 22    (Verification Case g)**Robust Case     |
      Test Case   - 23    (Verification Case h)                  |
      Test Case   - 24    (Verification Case i)------------------|

      Test Case   - 25    (Verification Case a)------------------|
      Test Case   - 26    (Verification Case b)                  |
      Test Case   - 27    (Verification Case e)                  |For
      Test Case   - 28    (Verification Case c & d)              |parameter
      Test Case   - 29    (Verification Case f)                  |equip_cool_sw
      Test Case   - 30    (Verification Case g)**Robust Case     |
      Test Case   - 31    (Verification Case h)                  |
      Test Case   - 32    (Verification Case i)------------------|

      Test Case   - 33    (Verification Case a)------------------|
      Test Case   - 34    (Verification Case b)                  |
      Test Case   - 35    (Verification Case e)                  |For
      Test Case   - 36    (Verification Case c & d)              |parameter
      Test Case   - 37    (Verification Case f)                  |gnd_test_data
      Test Case   - 38    (Verification Case g)**Robust Case     |_load_sw
      Test Case   - 39    (Verification Case h)                  |
      Test Case   - 40    (Verification Case i)------------------|

      Test Case   - 41    (Verification Case a)------------------|
      Test Case   - 42    (Verification Case b)                  |
      Test Case   - 43    (Verification Case e)                  |For
      Test Case   - 44    (Verification Case c & d)              |parameter
      Test Case   - 45    (Verification Case f)                  |engine_run
      Test Case   - 46    (Verification Case g)**Robust Case     |
      Test Case   - 47    (Verification Case h)                  |
      Test Case   - 48    (Verification Case i)------------------|

      Test Case   - 49    (Verification Case a)------------------|
      Test Case   - 50    (Verification Case b)                  |
      Test Case   - 51    (Verification Case e)                  |For
      Test Case   - 52    (Verification Case c & d)              |parameter
      Test Case   - 53    (Verification Case f)                  |total_air_temp
      Test Case   - 54    (Verification Case g)**Robust Case     |
      Test Case   - 55    (Verification Case h)                  |
      Test Case   - 56    (Verification Case i)------------------|

    -----------------------------------------------------------------
    Test Note:
    2a.update rate specified in table 3.2.2.1.3.1.2.2-2 of Channel Signal
    Selection is verified in s3_2_2_1_3_1_2_2_Emulator.grp script.

    -----------------------------------------------------------------
    '''
    testcase = 0
    UUT_list = ['lctc1']
    aircraft_type_list = ['passenger','freighter']
    # aircraft_type_list = ['passenger']
    testpoint = 1
    input_parameter_validity_table = [
    ('flight_phase_lss_v', 'flight_phase_lss',1,'flight_phase_lss_v_oc',\
       'flight_phase_lss_oc', 'flight_phase_data_def', 'flight_phase_v',\
       'flight_phase', 'l_409_w03_p_raw', 'flight_phase_p_v', \
       'flight_phase_s_v', 3,1,7,'flight_number_p1_data_def'),\
     ('baro_altitude_lss_v', 'baro_altitude_lss',0.01,'baro_altitude_lss_v_oc',\
       'baro_altitude_lss_oc', 'baro_altitude_data_def', 'baro_altitude_v',\
       'baro_altitude', 'l_70a_w04_p_raw', 'baro_altitude_p_v', \
       'baro_altitude_s_v', 121,512,22,'baro_altitude_lss_data_def'),\
     ('gnd_speed_lss_v', 'gnd_speed_lss',0.125,'gnd_speed_lss_v_oc',\
       'gnd_speed_lss_oc', 'gnd_speed_data_def', 'gnd_speed_v',\
       'gnd_speed', 'l_eae_w11_p_raw', 'gnd_speed_p_v', \
       'gnd_speed_s_v', 13,128,0,'gnd_speed_lss_data_def'),\
     ('equip_cool_sw_lss_v', 'equip_cool_sw_lss',1/64,'equip_cool_sw_lss_v_oc',\
       'equip_cool_sw_lss_oc', 'equip_cool_sw_def', 'equip_cool_sw_v',\
       'equip_cool_sw', 'l_e77_w03_p_raw', 'equip_cool_and_voc_p_v', \
       'equip_cool_and_voc_s_v', 3,64,2,'equip_cool_sw_lss_def'),\
     ('gnd_test_data_load_sw_lss_v', 'gnd_test_data_load_sw_lss',1/256,\
       'gnd_test_data_load_sw_lss_v_oc','gnd_test_data_load_sw_lss_oc',\
       'gnd_test_data_load_sw_def', 'gnd_test_data_load_sw_v',\
       'gnd_test_data_load_sw', 'l_ea4_w02_p_raw', 'gnd_test_data_load_p_v',\
       'gnd_test_data_load_s_v', 1,1024,2,'gnd_test_data_load_sw_lss_def'),\
     ('engine_run_lss_v','engine_run_lss',1/2048,\
       'engine_run_lss_v_oc','engine_run_lss_oc', \
       'engine_run_data_def', 'engine_run_v','engine_run',  \
       'l_eb0_w10_p_raw', 'engine_running_l_p_v','engine_running_l_s_v', \
       1,2048,0,'engine_idle_l_def'),\
        ('total_air_temp_lss_v','total_air_temp_lss',0.125,\
       'total_air_temp_lss_v_oc','total_air_temp_lss_oc', \
       'total_air_temp_data_def', 'total_air_temp_v','total_air_temp',  \
       'l_fed_w07_p_raw', 'total_air_temp_p_v','total_air_temp_s_v', \
       -15.0,1024,-100.0,'total_air_temp_lss_data_def'),\
     #Newly added
        ('flow_priority_sw_lss_v','flow_priority_sw_lss',2/512,\
       'flow_priority_sw_lss_v_oc','flow_priority_sw_lss_oc', \
       'flow_priority_sw_def', 'flow_priority_sw_v','flow_priority_sw',  \
       'l_e77_w03_p_raw', 'equip_cool_and_voc_p_v','equip_cool_and_voc_s_v', \
       0,512,0,'flow_priority_sw_lss_def')\
       ]
    for aircraft_type_signal in aircraft_type_list:
        for UUT in UUT_list:
            UUT += '::'
            u.WriteToLog('#-- Req 2a Test start for channel: ' + UUT + ' for ' +\
            aircraft_type_signal + '--#', color='green')
            u.WriteToLog('Building the signals')

            #Signals
            k_css_no_info_time  = UUT + 'k_css_no_info_time'

            k_disable_all_label_aquisition_inputs =\
                                    UUT + 'k_disable_all_label_aquisition_inputs'
            k_disable_all_can_inputs  = UUT + 'k_disable_all_can_inputs'
            aircraft_type = UUT + 'aircraft_type'
            if (aircraft_type_signal == 'freighter'):
                u.SetSignal(aircraft_type, 8)
                u.sleep(1)
                u.CheckSignal(aircraft_type, 8)
            else:
                u.SetSignal(aircraft_type, 7)
                u.sleep(1)
                u.CheckSignal(aircraft_type, 7)
            #Set disable Signals
            u.SetSignal(k_disable_all_label_aquisition_inputs,1)
            u.SetSignal(k_disable_all_can_inputs,1)
            u.sleep(1)
            u.CheckSignal(k_disable_all_label_aquisition_inputs,1)
            u.CheckSignal(k_disable_all_can_inputs,1)

            #Verify constants to default value Signals
            u.CheckSignal(k_css_no_info_time, 5)

            for (validity1, parameter1, resolution, validity2, parameter2, \
                defaultflag, opV, opP, inputdata, primV,secV,lesstol,\
                set_value1, initial_value,defaultflagloc) in \
                input_parameter_validity_table:

                #CTC Input data, validity, parameter and default flag
                validity_local = UUT + validity1
                parameter_local = UUT + parameter1
                validity_oth = UUT + validity2
                parameter_oth = UUT + parameter2
                default_flag = UUT + defaultflag
                output_V = UUT + opV
                output_P = UUT + opP
                ctc_input_data = UUT + inputdata
                primary_V = UUT + primV
                secondary_V = UUT + secV
                default_flag_loc = UUT + defaultflagloc

                u.WriteToLog('---- Requirement 2a is Started----',\
                    color='green')
                if opP == 'flight_phase':
                    u.WriteToLog('---- For Parameter Flight_Phase ----',\
                    color='orange')
                elif opP == 'baro_altitude':
                    u.WriteToLog('---- For Parameter Baro_Altitude ----',\
                    color='orange')
                elif opP == 'gnd_speed':
                    u.WriteToLog('---- For Parameter Gnd_Speed ----',\
                    color='orange')
                elif opP == 'equip_cool_sw':
                    u.WriteToLog('---- For Parameter Equip_Cool_Sw ----',\
                    color='orange')
                elif opP == 'gnd_test_data_load_sw':
                    u.WriteToLog('---- For Parameter Gnd_Test_Data_Load_Sw ----',\
                    color='orange')
                elif opP == 'engine_run':
                    u.WriteToLog('---- For Parameter Engine_Run ----',\
                    color='orange')
                elif opP == 'total_air_temp':
                    u.WriteToLog('---- For Parameter Total_Air_Temp ----',\
                    color='orange')
                else:
                    u.WriteToLog('---- For Parameter Flow_Priority_Sw ----',\
                    color='orange')

                ''' - ProcStep 1
                Set primary_V to False
                Set secondary_V to False
                Set ctc_input_data to set_value1
                Set validity_oth to True
                Set parameter_oth to lesstol
                Wait for 1 second
                Verify output_V is set to True
                Verify output_P is set to lesstol
                Set primary_V to False
                Set validity_oth to False
                Wait for 1 second
                Verify output_V is set to False
                Verify output_P is set to lesstol
                Verify default_flag is set to False
                '''
                u.WriteToLog('---- Check outputs are set to different value before '
                + 'checking their initial Test case value ----', color='green')
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
    #     ('flow_priority_sw_lss_v','flow_priority_sw_lss',2/512,\
    #    'flow_priority_sw_lss_v_oc','flow_priority_sw_lss_oc', \
    #    'flow_priority_sw_def', 'flow_priority_sw_v','flow_priority_sw',  \
    #    'l_e77_w03_p_raw', 'equip_cool_and_voc_p_v','equip_cool_and_voc_s_v', \
    #    0,512,0,'flow_priority_sw_lss_def')
                #------------------------------ 1-----------------------------------
                testcase += 1
                u.SetTestCase(testpoint, testcase, type='normal')
                '''- ProcTrace 1
                ProcSteps 2 to 4 verifies
                Test Case 1, 9, 17, 25, 33, 41, 49 for LCTC1
                '''
                ''' - ProcStep 2
                Set primary_V to True
                Set secondary_V to False
                Set ctc_input_data to set_value1
                Set validity_oth to False
                Set parameter_oth to lesstol
                Wait for 1 second
                Set expected_output to ((64 * resolution * 1.8) + 32.0) when
                resolution is 0.125 and initial_value is -100.0:
                Set expected_output to (64 * resolution ) when resolution is 0.01
                Set expected_output to (set_value1 * resolution) for other values
                '''
                u.WriteToLog(' ---- Setting the Test Condition for Verification '
                    + 'case a ----', color='green')

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

                ''' - ProcStep 3
                Verify parameter_local is set to expected_output
                Verify default_flag is set to False
                Verify validity_local is set to True
                Verify validity_oth is set to False
                Verify parameter_oth is set to lesstol
                '''
                u.WriteToLog(' ---- Verifying the Test Condition for Verification '
                    + 'case a ----', color='green')
                u.CheckSignal(parameter_local, expected_output)
                u.CheckSignal(default_flag, 0)
                u.CheckSignal(validity_local, 1)
                u.CheckSignal(validity_oth, 0)
                u.CheckSignal(parameter_oth, lesstol)
                if (aircraft_type_signal == 'freighter'):
                    u.CheckSignal(aircraft_type, 8)
                else:
                    u.CheckSignal(aircraft_type, 7)
                ''' - ProcStep 4
                Verify output_V is set to True
                Verify output_P is set to expected_output
                '''
                u.WriteToLog(' ---- Verifying the Output Signals for Verification '
                    + 'case a ----', color='green')
                u.CheckSignal(output_V, 1)
                u.CheckSignal(output_P, expected_output)

                #------------------------------ 2-----------------------------------
                testcase += 1
                u.SetTestCase(testpoint, testcase, type='normal')
                '''- ProcTrace 2
                ProcSteps 5 to 7 verifies
                Test Case 2, 10, 18, 26, 34, 42, 50 for LCTC1
                '''
                ''' - ProcStep 5
                Set primary_V to False
                Set validity_oth to True
                Set parameter_oth to lesstol
                Wait for 1 second
                '''
                u.WriteToLog(' ---- Setting the Test Condition for Verification '
                    + 'case b ----', color='green')
                u.SetSignal(primary_V, 0)
                u.SetSignal(validity_oth, 1)
                u.SetSignal(parameter_oth, lesstol)
                u.sleep(1)

                ''' - ProcStep 6
                Verify parameter_local is set to expected_output
                Verify parameter_oth is set to lesstol
                Verify default_flag is set to False
                Verify validity_local is set to False
                Verify validity_oth is set to True
                '''
                u.WriteToLog(' ---- Verifying the Test Condition for Verification '
                    + 'case b ----', color='green')
                if (aircraft_type_signal == 'freighter'):
                    u.CheckSignal(aircraft_type, 8)
                else:
                    u.CheckSignal(aircraft_type, 7)
                u.CheckSignal(parameter_local, expected_output)
                u.CheckSignal(parameter_oth, lesstol)
                u.CheckSignal(default_flag, 0)
                u.CheckSignal(validity_local, 0)
                u.CheckSignal(validity_oth, 1)

                ''' - ProcStep 7
                Verify output_V is set to True
                Verify output_P to lesstol
                '''
                u.WriteToLog(' ---- Verifying the Output Signals for Verification '
                    + 'case b ----', color='green')
                u.CheckSignal(output_V, 1)
                u.CheckSignal(output_P, lesstol)

                ''' - ProcStep 8
                Set default_flag_loc to False
                Set primary_V to False
                Set validity_oth to False
                Wait for 6 seconds
                Verify output_V is set to False
                Verify output_P is set to initial_value
                '''
                u.SetSignal(default_flag_loc, 0)
                u.SetSignal(primary_V, 0)
                u.SetSignal(validity_oth, 0)
                u.sleep(6)
                u.CheckSignal(output_V, 0)
                u.CheckSignal(output_P, initial_value)

                #------------------------------ 3-----------------------------------
                testcase += 1
                u.SetTestCase(testpoint, testcase, type='normal')
                '''- ProcTrace 3
                ProcSteps 9 to 10 verifies
                Test Case 3, 11, 19, 27, 35, 43, 51 for LCTC1
                '''
                ''' - ProcStep 9
                Set default_flag_loc to False
                Set primary_V to True
                Set validity_oth to False
                Set parameter_oth to lesstol
                Wait for 4 seconds
                '''
                u.WriteToLog(' ---- Setting the Test Condition for Verification '
                    + 'case e ----', color='green')
                u.SetSignal(default_flag_loc, 0)
                u.SetSignal(primary_V, 1)
                u.SetSignal(validity_oth, 0)
                u.SetSignal(parameter_oth, lesstol)
                u.sleep(4)

                ''' - ProcStep 10
                Verify default_flag is set to True
                Verify output_V is set to True
                Verify output_P is set to initial_value
                Wait for 2 seconds
                Verify parameter_local is set to expected_output
                Verify primary_V is set to True
                Verify ctc_input_data is set to set_value1
                Verify validity_local is set to True
                Verify validity_oth is set to False
                Verify parameter_oth is set to lesstol
                Manually verify output_V, output_P and default_flag when
                validity_local is True for K_CSS_No_Info_Time seconds
                Verify output_V is set to True
                Verify output_P is set to expected_output
                Verify default_flag is set to False
                '''
                u.WriteToLog(' ---- Verifying the Test Condition for Verification '
                    + 'case e ----', color='green')
                u.CheckSignal(default_flag, 1)
                u.CheckSignal(output_V, 1)
                u.CheckSignal(output_P, initial_value)
                u.sleep(2)
                if (aircraft_type_signal == 'freighter'):
                    u.CheckSignal(aircraft_type, 8)
                else:
                    u.CheckSignal(aircraft_type, 7)
                u.CheckSignal(parameter_local, expected_output)
                u.CheckSignal(primary_V, 1)
                u.CheckSignal(ctc_input_data, set_value1)
                u.CheckSignal(validity_local, 1)
                u.CheckSignal(validity_oth, 0)
                u.CheckSignal(parameter_oth, lesstol)
                u.WriteToLog(' ---- Verifying the Output Signals for Verification '
                    + 'case e ----', color='green')
                u.PostProcess('Manually verify output_V, output_P and default_flag '
                + 'when validity_local is True for '
                + 'K_CSS_No_Info_Time seconds in csv record file '
                + 's3_2_2_1_3_1_2_2__2a')
                u.CheckSignal(output_V, 1)
                u.CheckSignal(output_P, expected_output)
                u.CheckSignal(default_flag, 0)

                #------------------------------ 4-----------------------------------
                testcase += 1
                u.SetTestCase(testpoint, testcase, type='normal')
                '''- ProcTrace 4
                ProcSteps 11 to 14 verifies
                Test Case 4, 12, 20, 28, 36, 44, 52 for LCTC1
                '''
                ''' - ProcStep 11
                Set validity_oth to False
                Set primary_V to False
                Wait for 4 seconds
                '''
                u.WriteToLog(' ---- Setting the Test Condition for Verification '
                    + 'case c and d ----', color='green')
                u.SetSignal(primary_V, 0)
                u.SetSignal(validity_oth, 0)
                u.sleep(4)

                ''' - ProcStep 12
                Verify validity_oth is set to False
                Verify default_flag is set to False
                Verify validity_local is set to False
                '''
                u.WriteToLog(' ---- Verifying the Test Condition for Verification '
                    + 'case c ----', color='green')
                if (aircraft_type_signal == 'freighter'):
                    u.CheckSignal(aircraft_type, 8)
                else:
                    u.CheckSignal(aircraft_type, 7)
                u.CheckSignal(validity_oth, 0)
                u.CheckSignal(default_flag, 0)
                u.CheckSignal(validity_local, 0)

                ''' - ProcStep 13
                Verify output_V is set to False
                Verify output_P is set to expected_output
                '''
                u.WriteToLog(' ---- Verifying the Output Signals for Verification '
                    + 'case c ----', color='green')
                u.CheckSignal(output_V, 0)
                u.CheckSignal(output_P, expected_output)

                ''' - ProcStep 14
                Verify validity_oth is set to False
                Verify default_flag is set to False
                Verify validity_local is set to False
                Wait for 2 seconds
                Manually verify output_V, output_P and default_flag when
                validity_oth and validity_local are False for K_CSS_No_Info_Time
                seconds
                Verify output_V is set to False
                Verify output_P to initial_value
                Verify default_flag to True
                '''
                u.WriteToLog(' ---- Verifying the Test Condition for Verification '
                    + 'case d ----', color='green')
                if (aircraft_type_signal == 'freighter'):
                    u.CheckSignal(aircraft_type, 8)
                else:
                    u.CheckSignal(aircraft_type, 7)
                u.CheckSignal(validity_oth, 0)
                u.CheckSignal(default_flag, 0)
                u.CheckSignal(validity_local, 0)
                u.sleep(2)
                u.WriteToLog(' ---- Verifying the Output Signals for Verification '
                    + 'case d ----', color='green')
                u.PostProcess('Manually verify output_V, output_P and default_flag '
                + 'when validity_oth and validity_local are False for '
                + 'K_CSS_No_Info_Time seconds in csv record file '
                + 's3_2_2_1_3_1_2_2__2a')
                u.CheckSignal(output_V, 0)
                u.CheckSignal(output_P, initial_value)
                u.CheckSignal(default_flag, 1)

                #------------------------------ 5-----------------------------------
                testcase += 1
                u.SetTestCase(testpoint, testcase, type='normal')
                '''- ProcTrace 5
                ProcSteps 15 to 17 verifies
                Test Case 5, 13, 21, 29, 37, 45, 53 for LCTC1
                '''
                ''' - ProcStep 15
                Set default_flag_loc to False
                Set validity_oth to True
                Set primary_V to False
                Set parameter_oth to lesstol
                Wait for 4 seconds
                '''
                u.WriteToLog(' ---- Setting the Test Condition for Verification '
                    + 'case f ----', color='green')
                u.SetSignal(default_flag_loc, 0)
                u.SetSignal(validity_oth, 1)
                u.SetSignal(primary_V, 0)
                u.SetSignal(parameter_oth, lesstol)
                u.sleep(4)

                ''' - ProcStep 16
                Verify validity_oth is set to True
                Verify default_flag is set to True
                Verify validity_local is set to False
                Verify parameter_oth is set to lesstol
                '''
                u.WriteToLog(' ---- Verifying the Test Condition for Verification '
                    + 'case f ----', color='green')
                if (aircraft_type_signal == 'freighter'):
                    u.CheckSignal(aircraft_type, 8)
                else:
                    u.CheckSignal(aircraft_type, 7)
                u.CheckSignal(validity_oth, 1)
                u.CheckSignal(default_flag, 1)
                u.CheckSignal(validity_local, 0)
                u.CheckSignal(parameter_oth, lesstol)

                ''' - ProcStep 17
                Verify output_V is set to True
                Verify output_P is set to initial_value
                Verify default_flag is set to True
                Wait for 2 seconds
                Manually verify output_V, output_P and default_flag when
                validity_oth is True and validity_local is False for
                K_CSS_No_Info_Time seconds
                Verify output_V is set to True
                Verify output_P is set to lesstol
                Verify default_flag is set to False
                '''
                u.WriteToLog(' ---- Verifying the Output Signals for Verification '
                    + 'case f ----', color='green')
                u.CheckSignal(output_V, 1)
                u.CheckSignal(output_P, initial_value)
                u.CheckSignal(default_flag, 1)
                u.sleep(2)
                u.PostProcess('Manually verify output_V, output_P and default_flag '
                + 'when validity_oth is True and validity_local is False for '
                + 'K_CSS_No_Info_Time seconds in csv record file '
                + 's3_2_2_1_3_1_2_2__2a')
                u.CheckSignal(output_V, 1)
                u.CheckSignal(output_P, lesstol)
                u.CheckSignal(default_flag, 0)

                ''' - ProcStep 18
                Set k_css_no_info_time to 3
                Set default_flag_loc to False
                Set validity_oth to False
                Set primary_V to False
                Wait for 4 seconds
                Verify output_V is set to False
                Verify output_P is set to initial_value
                '''
                u.SetSignal(k_css_no_info_time, 3)
                u.SetSignal(default_flag_loc, 0)
                u.SetSignal(primary_V, 0)
                u.SetSignal(validity_oth, 0)
                u.sleep(4)
                u.CheckSignal(output_V, 0)
                u.CheckSignal(output_P, initial_value)

                #------------------------------ 6-----------------------------------
                testcase += 1
                u.SetTestCase(testpoint, testcase, type='robust')
                '''- ProcTrace 6
                ProcSteps 19 to 21 verifies
                Test Case 6, 14, 22, 30, 38, 46, 54 for LCTC1
                '''
                ''' - ProcStep 19
                Set default_flag_loc to False
                Set validity_oth to True
                Set primary_V to False
                Set parameter_oth to lesstol
                Wait for 2 seconds
                '''
                u.WriteToLog(' ---- Setting the Test Condition for Verification '
                    + 'case g ----', color='green')
                u.SetSignal(default_flag_loc, 0)
                u.SetSignal(validity_oth, 1)
                u.SetSignal(primary_V, 0)
                u.SetSignal(parameter_oth, lesstol)
                u.sleep(2)

                ''' - ProcStep 20
                Verify k_css_no_info_time is set to 3
                Verify validity_oth is set to True
                Verify default_flag is set to True
                Verify validity_local is set to False
                Verify parameter_oth is set to lesstol
                '''
                u.WriteToLog(' ---- Verifying the Test Condition for Verification '
                    + 'case g ----', color='green')
                if (aircraft_type_signal == 'freighter'):
                    u.CheckSignal(aircraft_type, 8)
                else:
                    u.CheckSignal(aircraft_type, 7)
                u.CheckSignal(k_css_no_info_time, 3)
                u.CheckSignal(validity_oth, 1)
                u.CheckSignal(default_flag, 1)
                u.CheckSignal(validity_local, 0)
                u.CheckSignal(parameter_oth, lesstol)

                ''' - ProcStep 21
                Verify output_V is set to True
                Verify output_P is set to initial_value
                Verify default_flag is set to True
                Wait for 2 seconds
                Verify output_V is set to True
                Verify output_P is set to lesstol
                Verify default_flag is set to False
                '''
                u.WriteToLog(' ---- Verifying the Output Signals for Verification '
                    + 'case g ----', color='green')
                u.CheckSignal(output_V, 1)
                u.CheckSignal(output_P, initial_value)
                u.CheckSignal(default_flag, 1)
                u.sleep(2)
                u.CheckSignal(output_V, 1)
                u.CheckSignal(output_P, lesstol)
                u.CheckSignal(default_flag, 0)

                #Re-trim k_css_no_info_time constat to default value 5
                ''' - ProcStep 22
                Set k_css_no_info_time to 5
                Wait for 1 second
                Verify k_css_no_info_time is set to 5
                '''
                u.SetSignal(k_css_no_info_time, 5)
                u.sleep(1)
                u.CheckSignal(k_css_no_info_time, 5)

                #------------------------------ 7-----------------------------------
                testcase += 1
                u.SetTestCase(testpoint, testcase, type='normal')
                '''- ProcTrace 7
                ProcSteps 23 to 25 verifies
                Test Case 7, 15, 23, 31, 39, 47, 55 for LCTC1
                '''
                ''' - ProcStep 23
                Set default_flag_loc to False
                Set primary_V to True
                Set validity_oth to True
                Set parameter_oth to lesstol
                Wait for 1 second
                '''
                u.WriteToLog(' ---- Setting the Test Condition for Verification '
                    + 'case h ----', color='green')
                u.SetSignal(default_flag_loc, 0)
                u.SetSignal(primary_V, 1)
                u.SetSignal(validity_oth, 1)
                u.SetSignal(parameter_oth, lesstol)
                u.sleep(1)

                ''' - ProcStep 24
                Verify parameter_local is set to expected_output
                Verify default_flag is set to False
                Verify validity_local is set to True
                Verify validity_oth is set to True
                Verify parameter_oth is set to lesstol
                '''
                u.WriteToLog(' ---- Verifying the Test Condition for Verification '
                    + 'case h ----', color='green')
                if (aircraft_type_signal == 'freighter'):
                    u.CheckSignal(aircraft_type, 8)
                else:
                    u.CheckSignal(aircraft_type, 7)
                u.CheckSignal(parameter_local, expected_output)
                u.CheckSignal(default_flag, 0)
                u.CheckSignal(validity_local, 1)
                u.CheckSignal(validity_oth, 1)
                u.CheckSignal(parameter_oth, lesstol)

                ''' - ProcStep 25
                Verify output_V is set to True
                Verify output_P is set to expected_output
                '''
                u.WriteToLog(' ---- Verifying the Output Signals for Verification '
                    + 'case h ----', color='green')
                u.CheckSignal(output_V, 1)
                u.CheckSignal(output_P, expected_output)

                ''' - ProcStep 26
                Set default_flag_loc to False
                Set validity_oth to False
                Set primary_V to False
                Wait for 6 seconds
                Verify output_V is set to False
                Verify output_P is set to initial_value
                '''
                u.SetSignal(default_flag_loc, 0)
                u.SetSignal(primary_V, 0)
                u.SetSignal(validity_oth, 0)
                u.sleep(6)
                u.CheckSignal(output_V, 0)
                u.CheckSignal(output_P, initial_value)

                #------------------------------ 8-----------------------------------
                testcase += 1
                u.SetTestCase(testpoint, testcase, type='normal')
                '''- ProcTrace 8
                ProcSteps 27 to 28 verifies
                Test Case 8, 16, 24, 32, 40, 48, 56 for LCTC1
                '''
                ''' - ProcStep 27
                Set default_flag_loc to False
                Set primary_V to True
                Set validity_oth to True
                Set parameter_oth to lesstol
                Wait for 4 seconds
                '''
                u.WriteToLog(' ---- Setting the Test Condition for Verification '
                    + 'case i ----', color='green')
                u.SetSignal(default_flag_loc, 0)
                u.SetSignal(primary_V, 1)
                u.SetSignal(validity_oth, 1)
                u.SetSignal(parameter_oth, lesstol)
                u.sleep(4)

                ''' - ProcStep 28
                Verify default_flag is set to True
                Verify output_V is set to True
                Verify output_P is set to initial_value
                Wait for 2 seconds
                Verify parameter_local is set to expected_output
                Verify primary_V is set to True
                Verify ctc_input_data is set to set_value1
                Verify validity_local is set to True
                Verify validity_oth is set to False
                Verify parameter_oth is set to lesstol
                Verify output_V is set to True
                Verify output_P is set to expected_output
                Verify default_flag is set to False
                '''
                u.WriteToLog(' ---- Verifying the Test Condition for Verification '
                    + 'case i ----', color='green')
                if (aircraft_type_signal == 'freighter'):
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
                u.WriteToLog(' ---- Verifying the Output Signals for Verification '
                    + 'case i ----', color='green')
                u.CheckSignal(output_V, 1)
                u.CheckSignal(output_P, expected_output)
                u.CheckSignal(default_flag, 0)
                #-------------------------------------------------------------------

                u.WriteToLog('---- Requirement 2a is complete----',\
                    color='green')
                if opP == 'flight_phase':
                    u.WriteToLog('---- For Parameter Flight_Phase ----',\
                    color='orange')
                elif opP == 'baro_altitude':
                    u.WriteToLog('---- For Parameter Baro_Altitude ----',\
                    color='orange')
                elif opP == 'gnd_speed':
                    u.WriteToLog('---- For Parameter Gnd_Speed ----',\
                    color='orange')
                elif opP == 'equip_cool_sw':
                    u.WriteToLog('---- For Parameter Equip_Cool_Sw ----',\
                    color='orange')
                elif opP == 'gnd_test_data_load_sw':
                    u.WriteToLog('---- For Parameter Gnd_Test_Data_Load_Sw ----',\
                    color='orange')
                elif opP == 'engine_run':
                    u.WriteToLog('---- For Parameter Engine_Run ----',\
                    color='orange')
                else:
                    u.WriteToLog('---- For Parameter Total_Air_Temp ----',\
                    color='orange')

        #-----------------------------------------------------------------------
        #Reset disable Signals
        u.SetSignal(k_disable_all_label_aquisition_inputs,0)
        u.SetSignal(k_disable_all_can_inputs,0)
        u.sleep(1)
        u.CheckSignal(k_disable_all_label_aquisition_inputs,0)
        u.CheckSignal(k_disable_all_can_inputs,0)
    #---------------------------------------------------------------------------


def reqt_2b_passenger_freighter():
    '''
    ----------------------------------------------------------------------------
    Requirement: 2b) Test Data flag logic

    Verification Cases:
    a)For Controller_Side = Left_Side AND Channel_Number = Channel_1 the test
      data flags shall be set as follows:lctc1

        Set FD_Sw_App_LSS_Test_Data to True
        Set FD_Sw_App_LSS_Test_Data_OC to False
        Set EICAS_LSS_Test_Data to True
        Set EICAS_LSS_Test_Data_OC to False
        Set ADIRU_LSS_Test_Data to True
        Set ADIRU_LSS_Test_Data_OC to False
        Set Gnd_Test_Sw_App_LSS_Test_Data to True
        Set Gnd_Test_Sw_App_LSS_Test_Data_OC to False
        Verify that the below signals are set:
            fd_sw_app_l_test_data to True
            fd_sw_app_r_test_data to False
            eicas_l_test_data to True
            eicas_r_test_data to False
            adiru_l_test_data to True
            adiru_r_test_data to False
            gnd_test_sw_app_l_test_data to True
            gnd_test_sw_app_r_test_data to False

        Set FD_Sw_App_LSS_Test_Data to False
        Set FD_Sw_App_LSS_Test_Data_OC to True
        Set EICAS_LSS_Test_Data to False
        Set EICAS_LSS_Test_Data_OC to True
        Set ADIRU_LSS_Test_Data to False
        Set ADIRU_LSS_Test_Data_OC to True
        Set Gnd_Test_Sw_App_LSS_Test_Data to False
        Set Gnd_Test_Sw_App_LSS_Test_Data_OC to True
        Verify that the below signals are set:
            fd_sw_app_l_test_data to False
            fd_sw_app_r_test_data to True
            eicas_l_test_data to False
            eicas_r_test_data to True
            adiru_l_test_data to False
            adiru_r_test_data to True
            gnd_test_sw_app_l_test_data to False
            gnd_test_sw_app_r_test_data to True


    b)For Controller_Side = Left_Side AND Channel_Number = Channel_2 the test
      data flags shall be set as follows:lctc2

        Set FD_Sw_App_LSS_Test_Data to True
        Set FD_Sw_App_LSS_Test_Data_OC to False
        Set EICAS_LSS_Test_Data to True
        Set EICAS_LSS_Test_Data_OC to False
        Set ADIRU_LSS_Test_Data to True
        Set ADIRU_LSS_Test_Data_OC to False
        Set Gnd_Test_Sw_App_LSS_Test_Data to True
        Set Gnd_Test_Sw_App_LSS_Test_Data_OC to False
        Verify that the below signals are set:
            fd_sw_app_l_test_data to False
            fd_sw_app_r_test_data to True
            eicas_l_test_data to False
            eicas_r_test_data to True
            adiru_l_test_data to False
            adiru_r_test_data to True
            gnd_test_sw_app_l_test_data to False
            gnd_test_sw_app_r_test_data to True

        Set FD_Sw_App_LSS_Test_Data to False
        Set FD_Sw_App_LSS_Test_Data_OC to True
        Set EICAS_LSS_Test_Data to False
        Set EICAS_LSS_Test_Data_OC to True
        Set ADIRU_LSS_Test_Data to False
        Set ADIRU_LSS_Test_Data_OC to True
        Set Gnd_Test_Sw_App_LSS_Test_Data to False
        Set Gnd_Test_Sw_App_LSS_Test_Data_OC to True
        Verify that the below signals are set:
            fd_sw_app_l_test_data to True
            fd_sw_app_r_test_data to False
            eicas_l_test_data to True
            eicas_r_test_data to False
            adiru_l_test_data to True
            adiru_r_test_data to False
            gnd_test_sw_app_l_test_data to True
            gnd_test_sw_app_r_test_data to False

    c)For Controller_Side = Right_Side AND Channel_Number = Channel_1 the test
      data flags shall be set as follows:

        Set FD_Sw_App_LSS_Test_Data to True
        Set FD_Sw_App_LSS_Test_Data_OC to False
        Set EICAS_LSS_Test_Data to True
        Set EICAS_LSS_Test_Data_OC to False
        Set ADIRU_LSS_Test_Data to True
        Set ADIRU_LSS_Test_Data_OC to False
        Set Gnd_Test_Sw_App_LSS_Test_Data to True
        Set Gnd_Test_Sw_App_LSS_Test_Data_OC to False
        Verify that the below signals are set:
            fd_sw_app_l_test_data to False
            fd_sw_app_r_test_data to True
            eicas_l_test_data to False
            eicas_r_test_data to True
            adiru_l_test_data to False
            adiru_r_test_data to True
            gnd_test_sw_app_l_test_data to False
            gnd_test_sw_app_r_test_data to True

        Set FD_Sw_App_LSS_Test_Data to False
        Set FD_Sw_App_LSS_Test_Data_OC to True
        Set EICAS_LSS_Test_Data to False
        Set EICAS_LSS_Test_Data_OC to True
        Set ADIRU_LSS_Test_Data to False
        Set ADIRU_LSS_Test_Data_OC to True
        Set Gnd_Test_Sw_App_LSS_Test_Data to False
        Set Gnd_Test_Sw_App_LSS_Test_Data_OC to True
        Verify that the below signals are set:
            fd_sw_app_l_test_data to True
            fd_sw_app_r_test_data to False
            eicas_l_test_data to True
            eicas_r_test_data to False
            adiru_l_test_data to True
            adiru_r_test_data to False
            gnd_test_sw_app_l_test_data to True
            gnd_test_sw_app_r_test_data to False

    d)For Controller_Side = Right_Side AND Channel_Number = Channel_2 the test
      data flags shall be set as follows:

        Set FD_Sw_App_LSS_Test_Data to True
        Set FD_Sw_App_LSS_Test_Data_OC to False
        Set EICAS_LSS_Test_Data to True
        Set EICAS_LSS_Test_Data_OC to False
        Set ADIRU_LSS_Test_Data to True
        Set ADIRU_LSS_Test_Data_OC to False
        Set Gnd_Test_Sw_App_LSS_Test_Data to True
        Set Gnd_Test_Sw_App_LSS_Test_Data_OC to False
        Verify that the below signals are set:
            fd_sw_app_l_test_data to True
            fd_sw_app_r_test_data to False
            eicas_l_test_data to True
            eicas_r_test_data to False
            adiru_l_test_data to True
            adiru_r_test_data to False
            gnd_test_sw_app_l_test_data to True
            gnd_test_sw_app_r_test_data to False

        Set FD_Sw_App_LSS_Test_Data to False
        Set FD_Sw_App_LSS_Test_Data_OC to True
        Set EICAS_LSS_Test_Data to False
        Set EICAS_LSS_Test_Data_OC to True
        Set ADIRU_LSS_Test_Data to False
        Set ADIRU_LSS_Test_Data_OC to True
        Set Gnd_Test_Sw_App_LSS_Test_Data to False
        Set Gnd_Test_Sw_App_LSS_Test_Data_OC to True
        Verify that the below signals are set:
            fd_sw_app_l_test_data to False
            fd_sw_app_r_test_data to True
            eicas_l_test_data to False
            eicas_r_test_data to True
            adiru_l_test_data to False
            adiru_r_test_data to True
            gnd_test_sw_app_l_test_data to False
            gnd_test_sw_app_r_test_data to True


    Script Markers:
        Test Point  - 2 (Requirement 2b)
        Channel     -   lctc1  lctc2  rctc1  rctc2
        Test Case   -    1      -     -       -         (Verification a)
        Test Case   -    -      2     -       -         (Verification b)
        Test Case   -    -      -     3       -         (Verification c)
        Test Case   -    -      -     -       4         (Verification d)

    Test Note:
    2b.update rate specified in table 3.2.2.1.3.1.2.1-2 of Channel Signal
    Selection is verified in s3_2_2_1_3_1_2_2_Emulator.grp script.
    #---------------------------------------------------------------------------
    #### Verify Test Data flag logic ####
    #---------------------------------------------------------------------------
    '''
    UUT_list = ['lctc1','lctc2','rctc1','rctc2']
    aircraft_type_list = ['passenger','freighter']
    testpoint = 2
    testcase = 0

    # Start UI Recording (if necessary)
    if record_data:
        u.StartRecording('s3_2_2_1_3_1_2_2__2b',\
                            screen_name='s3_2_2_1_3_1_2_2__2b', rec_freq_hz=32)
    for aircraft_type_signal in aircraft_type_list:
        for UUT in UUT_list:
            u.WriteToLog('#-- Req 2b Test start for channel: ' + UUT + ' for ' +\
            aircraft_type_signal + '--#', color='green')
            UUT += '::'
            #building full signal strings
            controller_side = UUT + 'controller_side'
            channel_number = UUT + 'channel_number'
            fd_sw_app_l_test_data = UUT + 'fd_sw_app_l_test_data'
            fd_sw_app_r_test_data = UUT + 'fd_sw_app_r_test_data'
            eicas_l_test_data = UUT + 'eicas_l_test_data'
            eicas_r_test_data = UUT + 'eicas_r_test_data'
            adiru_l_test_data = UUT + 'adiru_l_test_data'
            adiru_r_test_data = UUT + 'adiru_r_test_data'
            gnd_test_sw_app_l_test_data = UUT + 'gnd_test_sw_app_l_test_data'
            gnd_test_sw_app_r_test_data = UUT + 'gnd_test_sw_app_r_test_data'
            fd_sw_app_lss_test_data = UUT + 'fd_sw_app_lss_test_data'
            fd_sw_app_lss_test_data_oc = UUT + 'fd_sw_app_lss_test_data_oc'
            eicas_lss_test_data = UUT + 'eicas_lss_test_data'
            eicas_lss_test_data_oc = UUT + 'eicas_lss_test_data_oc'
            adiru_lss_test_data = UUT + 'adiru_lss_test_data'
            adiru_lss_test_data_oc = UUT + 'adiru_lss_test_data_oc'
            gnd_test_sw_app_lss_test_data = UUT + 'gnd_test_sw_app_lss_test_data'
            gnd_test_sw_app_lss_test_data_oc = UUT + \
                                            'gnd_test_sw_app_lss_test_data_oc'
            fd_sw_app_p_test_data = UUT + 'fd_sw_app_p_test_data'
            eicas_p_test_data = UUT + 'eicas_p_test_data'
            adiru_p_test_data = UUT + 'adiru_p_test_data'
            gnd_test_sw_app_p_test_data = UUT + 'gnd_test_sw_app_p_test_data'
            adiru_r_test_data = UUT + 'adiru_r_test_data'
            k_disable_all_label_aquisition_inputs = UUT + \
            'k_disable_all_label_aquisition_inputs'
            k_disable_all_can_inputs = UUT + 'k_disable_all_can_inputs'
            aircraft_type = UUT + 'aircraft_type'
            if (aircraft_type_signal == 'freighter'):
                u.SetSignal(aircraft_type, 8)
                u.sleep(1)
                u.CheckSignal(aircraft_type, 8)
            else:
                u.SetSignal(aircraft_type, 7)
                u.sleep(1)
                u.CheckSignal(aircraft_type, 7)
            #----------------------------------------------------------------------
            u.WriteToLog('--- Setting Disable Flags ----')
            u.SetSignal(k_disable_all_label_aquisition_inputs, 1)
            u.SetSignal(k_disable_all_can_inputs, 1)
            u.sleep(1)
            u.CheckSignal(k_disable_all_label_aquisition_inputs, 1)
            u.CheckSignal(k_disable_all_can_inputs, 1)
            #----------------------------------------------------------------------
            u.WriteToLog('---- Check outputs are set to different value before '
            + 'checking their initial Test case value ----', color='green')
            u.SetSignal(fd_sw_app_p_test_data, 0)
            u.SetSignal(eicas_p_test_data, 0)
            u.SetSignal(adiru_p_test_data, 0)
            u.SetSignal(gnd_test_sw_app_p_test_data, 0)
            u.SetSignal(fd_sw_app_lss_test_data_oc, 1)
            u.SetSignal(eicas_lss_test_data_oc, 1)
            u.SetSignal(adiru_lss_test_data_oc, 1)
            u.SetSignal(gnd_test_sw_app_lss_test_data_oc, 1)
            u.sleep(1)

            if (UUT == 'lctc1::' or UUT == 'rctc2::'):
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
            #---------------------------Test Case 1 to 4----------------------------

            testcase += 1
            u.SetTestCase(testpoint, testcase, type='normal')
            '''- ProcTrace 1
                ProcStep 1 to 6 verifies
                Test Case 1 for lctc1
                Test Case 4 for rctc2
                ProcStep 7 to 12 verifies
                Test Case 2 for lctc2
                Test Case 3 for rctc1
            '''
            if (UUT == 'lctc1::' or UUT == 'rctc2::'):
                ''' - ProcStep 1
                Set and verify the below variables:
                fd_sw_app_p_test_data to 1
                eicas_p_test_data to 1
                adiru_p_test_data to 1
                gnd_test_sw_app_p_test_data to 1
                fd_sw_app_lss_test_data_oc to 0
                eicas_lss_test_data_oc to 0
                adiru_lss_test_data_oc to 0
                gnd_test_sw_app_lss_test_data_oc to 0
                wait for 1 second
                '''
                if (UUT == 'lctc1::'):
                    u.WriteToLog('--Set the Test Condition for Verification Case a'\
                    ,color='orange')
                else:
                    u.WriteToLog('--Set the Test Condition for Verification Case d'\
                    ,color='orange')
                u.SetSignal(fd_sw_app_p_test_data, 1)
                u.SetSignal(eicas_p_test_data, 1)
                u.SetSignal(adiru_p_test_data, 1)
                u.SetSignal(gnd_test_sw_app_p_test_data, 1)
                u.SetSignal(fd_sw_app_lss_test_data_oc, 0)
                u.SetSignal(eicas_lss_test_data_oc, 0)
                u.SetSignal(adiru_lss_test_data_oc, 0)
                u.SetSignal(gnd_test_sw_app_lss_test_data_oc, 0)
                u.sleep(1)

                ''' - ProcStep 2
                verify the below variables:
                Verify controller_side is set to left_side(1) for lctc1
                and Right_side (2) for rctc2
                Verify Channel_number is set to channel_2(2)) for rctc2
                and channel_1 (1) for lctc1
                fd_sw_app_lss_test_data to 1
                fd_sw_app_lss_test_data_oc to 0
                eicas_lss_test_data to 1
                eicas_lss_test_data_oc to 0
                adiru_lss_test_data to 1
                adiru_lss_test_data_oc to 0
                gnd_test_sw_app_lss_test_data to 1
                gnd_test_sw_app_lss_test_data_oc to 0
                '''
                if (UUT =='rctc2::'):
                    u.WriteToLog('--Verify the Test Condition for Verification Case'
                    + ' d',color='orange')
                    u.CheckSignal(controller_side, 2)
                    u.CheckSignal(channel_number, 2)
                else:
                    u.WriteToLog('--Verify the Test Condition for Verification Case'
                    + ' a',color='orange')
                    u.CheckSignal(controller_side, 1)
                    u.CheckSignal(channel_number, 1)
                if (aircraft_type_signal == 'freighter'):
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

                ''' - ProcStep 3
                Verify that the below signals are set when:
                    controller_side is set to left_side(1) for lctc1
                    and Right_side (2) for rctc2
                    Channel_number is set to channel_2(2)) for rctc2
                    and channel_1 (1) for lctc1
                fd_sw_app_l_test_data to fd_sw_app_lss_test_data
                fd_sw_app_r_test_data to fd_sw_app_lss_test_data_oc
                eicas_l_test_data to eicas_lss_test_data
                eicas_r_test_data to eicas_lss_test_data_oc
                adiru_l_test_data to adiru_lss_test_data
                adiru_r_test_data to adiru_lss_test_data_oc
                gnd_test_sw_app_l_test_data to gnd_test_sw_app_lss_test_data
                gnd_test_sw_app_r_test_data to gnd_test_sw_app_lss_test_data_oc
                '''
                if (UUT =='rctc2::'):
                    u.WriteToLog('--Verify the Test Outputs for Verification Case'
                        + ' d',color='orange')
                    u.CheckSignal(controller_side, 2)
                    u.CheckSignal(channel_number, 2)
                else:
                    u.WriteToLog('--Verify the Test Outputs for Verification Case'
                        + ' a',color='orange')
                    u.CheckSignal(controller_side, 1)
                    u.CheckSignal(channel_number, 1)
                if (aircraft_type_signal == 'freighter'):
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

                ''' - ProcStep 4
                Set and verify the below variables:
                fd_sw_app_p_test_data to 0
                eicas_p_test_data to 0
                adiru_p_test_data to 0
                gnd_test_sw_app_p_test_data to 0
                fd_sw_app_lss_test_data_oc to 1
                eicas_lss_test_data_oc to 1
                adiru_lss_test_data_oc to 1
                gnd_test_sw_app_lss_test_data_oc to 1
                wait for 1 second
                '''
                if (UUT == 'lctc1::'):
                    u.WriteToLog('--Set the Test Condition for Verification Case a'\
                    ,color='orange')
                else:
                    u.WriteToLog('--Set the Test Condition for Verification Case d'\
                    ,color='orange')
                u.SetSignal(fd_sw_app_p_test_data, 0)
                u.SetSignal(eicas_p_test_data, 0)
                u.SetSignal(adiru_p_test_data, 0)
                u.SetSignal(gnd_test_sw_app_p_test_data, 0)
                u.SetSignal(fd_sw_app_lss_test_data_oc, 1)
                u.SetSignal(eicas_lss_test_data_oc, 1)
                u.SetSignal(adiru_lss_test_data_oc, 1)
                u.SetSignal(gnd_test_sw_app_lss_test_data_oc, 1)
                u.sleep(1)

                ''' - ProcStep 5
                verify the below variables:
                Verify controller_side is set to left_side(1) for lctc1
                and Right_side (2) for rctc2
                Verify Channel_number is set to channel_2(2)) for rctc2
                and channel_1 (1) for lctc1
                fd_sw_app_lss_test_data to 0
                fd_sw_app_lss_test_data_oc to 1
                eicas_lss_test_data to 0
                eicas_lss_test_data_oc to 1
                adiru_lss_test_data to 0
                adiru_lss_test_data_oc to 1
                gnd_test_sw_app_lss_test_data to 0
                gnd_test_sw_app_lss_test_data_oc to 1
                '''
                if (UUT =='rctc2::'):
                    u.WriteToLog('--Verify the Test Condition for Verification Case'
                        + ' d',color='orange')
                    u.CheckSignal(controller_side, 2)
                    u.CheckSignal(channel_number, 2)
                else:
                    u.WriteToLog('--Verify the Test Condition for Verification Case'
                        + ' a',color='orange')
                    u.CheckSignal(controller_side, 1)
                    u.CheckSignal(channel_number, 1)
                if (aircraft_type_signal == 'freighter'):
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

                ''' - ProcStep 6
                Verify that the below signals are set when
                    controller_side is set to left_side(1) for lctc1
                    and Right_side (2) for rctc2
                    Channel_number is set to channel_2(2)) for rctc2
                    and channel_1 (1) for lctc1
                fd_sw_app_l_test_data to fd_sw_app_lss_test_data
                fd_sw_app_r_test_data to fd_sw_app_lss_test_data_oc
                eicas_l_test_data to eicas_lss_test_data
                eicas_r_test_data to eicas_lss_test_data_oc
                adiru_l_test_data to adiru_lss_test_data
                adiru_r_test_data to adiru_lss_test_data_oc
                gnd_test_sw_app_l_test_data to gnd_test_sw_app_lss_test_data
                gnd_test_sw_app_r_test_data to gnd_test_sw_app_lss_test_data_oc
                '''
                if (UUT =='rctc2::'):
                    u.WriteToLog('--Verify the Test Outputs for Verification Case'
                        + ' d',color='orange')
                    u.CheckSignal(controller_side, 2)
                    u.CheckSignal(channel_number, 2)
                else:
                    u.WriteToLog('--Verify the Test Outputs for Verification Case'
                        + ' a',color='orange')
                    u.CheckSignal(controller_side, 1)
                    u.CheckSignal(channel_number, 1)
                if (aircraft_type_signal == 'freighter'):
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

            elif (UUT == 'lctc2::' or UUT == 'rctc1::'):
                ''' - ProcStep 7
                Set and verify the below variables:
                fd_sw_app_p_test_data to 1
                eicas_p_test_data to 1
                adiru_p_test_data to 1
                gnd_test_sw_app_p_test_data to 1
                fd_sw_app_lss_test_data_oc to 0
                eicas_lss_test_data_oc to 0
                adiru_lss_test_data_oc to 0
                gnd_test_sw_app_lss_test_data_oc to 0
                wait for 1 second
                '''
                if (UUT == 'lctc2::'):
                    u.WriteToLog('--Set the Test Condition for Verification Case b'\
                    ,color='orange')
                else:
                    u.WriteToLog('--Set the Test Condition for Verification Case c'\
                    ,color='orange')
                u.SetSignal(fd_sw_app_p_test_data, 1)
                u.SetSignal(eicas_p_test_data, 1)
                u.SetSignal(adiru_p_test_data, 1)
                u.SetSignal(gnd_test_sw_app_p_test_data, 1)
                u.SetSignal(fd_sw_app_lss_test_data_oc, 0)
                u.SetSignal(eicas_lss_test_data_oc, 0)
                u.SetSignal(adiru_lss_test_data_oc, 0)
                u.SetSignal(gnd_test_sw_app_lss_test_data_oc, 0)
                u.sleep(1)
                ''' - ProcStep 8
                verify the below variables:
                Verify controller_side is set to left_side(1) for lctc2
                and Right_side (2) for rctc1
                Verify Channel_number is set to channel_2(2)) for lctc2
                and channel_1 (1) for rctc1
                fd_sw_app_lss_test_data to 1
                fd_sw_app_lss_test_data_oc to 0
                eicas_lss_test_data to 1
                eicas_lss_test_data_oc to 0
                adiru_lss_test_data to 1
                adiru_lss_test_data_oc to 0
                gnd_test_sw_app_lss_test_data to 1
                gnd_test_sw_app_lss_test_data_oc to 0
                '''

                if (UUT =='rctc1::'):
                    u.WriteToLog('--Verify the Test Condition for Verification Case'
                        + ' c',color='orange')
                    u.CheckSignal(controller_side, 2)
                    u.CheckSignal(channel_number, 1)
                else:
                    u.WriteToLog('--Verify the Test Condition for Verification Case'
                        + ' b',color='orange')
                    u.CheckSignal(controller_side, 1)
                    u.CheckSignal(channel_number, 2)
                if (aircraft_type_signal == 'freighter'):
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

                ''' - ProcStep 9
                Verify that the below signals are set when
                    controller_side is set to left_side(1) for lctc2
                    and Right_side (2) for rctc1
                    Channel_number is set to channel_2(2)) for lctc2
                    and channel_1 (1) for rctc1
                fd_sw_app_l_test_data to fd_sw_app_lss_test_data_oc
                fd_sw_app_r_test_data to fd_sw_app_lss_test_data
                eicas_l_test_data to eicas_lss_test_data_oc
                eicas_r_test_data to eicas_lss_test_data
                adiru_l_test_data to adiru_lss_test_data_oc
                adiru_r_test_data to adiru_lss_test_data
                gnd_test_sw_app_l_test_data to gnd_test_sw_app_lss_test_data_oc
                gnd_test_sw_app_r_test_data to gnd_test_sw_app_lss_test_data
                '''
                if (UUT =='rctc1::'):
                    u.WriteToLog('--Verify the Test Outputs for Verification Case'
                        + ' c',color='orange')
                    u.CheckSignal(controller_side, 2)
                    u.CheckSignal(channel_number, 1)
                else:
                    u.WriteToLog('--Verify the Test Outputs for Verification Case'
                        + ' b',color='orange')
                    u.CheckSignal(controller_side, 1)
                    u.CheckSignal(channel_number, 2)
                if (aircraft_type_signal == 'freighter'):
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

                ''' - ProcStep 10
                Set and verify the below variables:
                fd_sw_app_p_test_data to 0
                eicas_p_test_data to 0
                adiru_p_test_data to 0
                gnd_test_sw_app_p_test_data to 0
                fd_sw_app_lss_test_data_oc to 1
                eicas_lss_test_data_oc to 1
                adiru_lss_test_data_oc to 1
                gnd_test_sw_app_lss_test_data_oc to 1
                wait for 1 second
                '''
                if (UUT == 'lctc2::'):
                    u.WriteToLog('--Set the Test Condition for Verification Case b'\
                    ,color='orange')
                else:
                    u.WriteToLog('--Set the Test Condition for Verification Case c'\
                    ,color='orange')
                u.SetSignal(fd_sw_app_p_test_data, 0)
                u.SetSignal(eicas_p_test_data, 0)
                u.SetSignal(adiru_p_test_data, 0)
                u.SetSignal(gnd_test_sw_app_p_test_data, 0)
                u.SetSignal(fd_sw_app_lss_test_data_oc, 1)
                u.SetSignal(eicas_lss_test_data_oc, 1)
                u.SetSignal(adiru_lss_test_data_oc, 1)
                u.SetSignal(gnd_test_sw_app_lss_test_data_oc, 1)
                u.sleep(1)

                ''' - ProcStep 11
                verify the below variables:
                Verify controller_side is set to left_side(1) for lctc2
                and Right_side(2) for rctc1
                Verify Channel_number is set to channel_2(2) for lctc2
                and channel_1(1) for rctc1
                fd_sw_app_lss_test_data to 0
                fd_sw_app_lss_test_data_oc to 1
                eicas_lss_test_data to 0
                eicas_lss_test_data_oc to 1
                adiru_lss_test_data to 0
                adiru_lss_test_data_oc to 1
                gnd_test_sw_app_lss_test_data to 0
                gnd_test_sw_app_lss_test_data_oc to 1
                '''
                if (UUT =='rctc1::'):
                    u.WriteToLog('--Verify the Test Conditions for Verification Case'
                        + ' c',color='orange')
                    u.CheckSignal(controller_side, 2)
                    u.CheckSignal(channel_number, 1)
                else:
                    u.WriteToLog('--Verify the Test Conditions for Verification Case'
                        + ' b',color='orange')
                    u.CheckSignal(controller_side, 1)
                    u.CheckSignal(channel_number, 2)
                if (aircraft_type_signal == 'freighter'):
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

                ''' - ProcStep 12
                Verify that the below signals are set when
                    controller_side is set to left_side(1) for lctc2
                    and Right_side (2) for rctc1
                    Channel_number is set to channel_2(2)) for lctc2
                    and channel_1 (1) for rctc1
                fd_sw_app_l_test_data to fd_sw_app_lss_test_data_oc
                fd_sw_app_r_test_data to fd_sw_app_lss_test_data
                eicas_l_test_data to eicas_lss_test_data_oc
                eicas_r_test_data to eicas_lss_test_data
                adiru_l_test_data to adiru_lss_test_data_oc
                adiru_r_test_data to adiru_lss_test_data
                gnd_test_sw_app_l_test_data to gnd_test_sw_app_lss_test_data_oc
                gnd_test_sw_app_r_test_data to gnd_test_sw_app_lss_test_data
                '''
                if (UUT =='rctc1::'):
                    u.WriteToLog('--Verify the Test Outputs for Verification Case'
                        + ' c',color='orange')
                    u.CheckSignal(controller_side, 2)
                    u.CheckSignal(channel_number, 1)
                else:
                    u.WriteToLog('--Verify the Test Outputs for Verification Case'
                        + ' b',color='orange')
                    u.CheckSignal(controller_side, 1)
                    u.CheckSignal(channel_number, 2)
                if (aircraft_type_signal == 'freighter'):
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

        #----------------------------------------------------------------------
        u.WriteToLog('--- Clearing Disable Flags ----')
        u.SetSignal(k_disable_all_label_aquisition_inputs, 0)
        u.SetSignal(k_disable_all_can_inputs, 0)
        u.sleep(1)
        u.CheckSignal(k_disable_all_label_aquisition_inputs, 0)
        u.CheckSignal(k_disable_all_can_inputs, 0)
        #----------------------------------------------------------------------
    if record_data:
      u.StopRecording()

    u.WriteToLog('--- The 2b requirement is complete---',color='orange')
#---------------------------Test Case 2---------------------------------

if __name__ == '__main__':
    # Upon script invocation:
    # Run actual test script
    run_script()