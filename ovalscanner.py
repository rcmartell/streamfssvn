import openscap, sys, os
from openscap import *

class OVAL_Scanner():
    def __init__(self):
        oscap_init()
        self.def_file = None
        self.def_model = None
        self.syschar_model = None
        self.session = None
        self.agent = None
        self.sysinfo = None
        self.res_model = None
        self.res_direct = None

    def callback(self, msg):
        print "definition: %s: %s" % (oscap_reporter_message_get_user1str(msg),
                                    oval_result_get_text(
                                    oscap_reporter_message_get_user2num(msg)))

    def evaluate_oval_defs(self, file):
        self.def_file = file
        self.def_model = oval_definition_model_import(def_file)
        self.syschar_model = oval_syschar_model_new(def_model)
        self.session = oval_probe_session_new(syschar_model)
        self.agent = oval_agent_new_session(def_model, "filename")
        self.sysinfo = oval_probe_query_sysinfo(session)
        oval_syschar_model_set_sysinfo(self.syschar_model, self.sysinfo)
        oval_agent_eval_system_py(self.agent, self.callback, None)
        self.res_model = oval_agent_get_results_model(self.agent)
        self.res_direct = oval_result_directives_new(self.res_model)
        oval_result_directives_set_reported(self.res_direct,
                                            OVAL_RESULT_TRUE |
                                            OVAL_RESULT_FALSE |
                                            OVAL_RESULT_UNKNOWN |
                                            OVAL_RESULT_ERROR |
                                            OVAL_RESULT_NOT_EVALUATED |
                                            OVAL_RESULT_NOT_APPLICABLE, True)

        oval_result_directives_set_content(self,res_direct,
                                           OVAL_RESULT_TRUE |
                                           OVAL_RESULT_FALSE |
                                           OVAL_RESULT_ERROR,
                                           OVAL_DIRECTIVE_CONTENT_FULL)
        oval_results_model_export(self.res_model, self.res_direct, sys.argv[2])
        oval_agent_destroy_session(self.agent)
        oval_definition_model_free(self.def_model)
        oval_result_directives_free(self.res_direct)
        oscap_cleanup()

if __name__ == "__main__":
    scanner = OVAL_Scanner()
    scanner.evaluate(sys.argv[1])
