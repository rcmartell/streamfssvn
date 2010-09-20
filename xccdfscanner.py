import openscap, sys, os
from openscap import *


class XCCDF_Scanner():
    def __init__(self):
        oscap_init()
        self.policy_iter = None
        self.policy = None
        self.benchmark = None
        self.policy_model = None

    def validate_xccdf_document(self, file):
        if not oscap_validate_document(file, OSCAP_DOCUMENT_XCCDF, None, None, None):
            print "Error: Not a valid XCCDF document."
            sys.exit(-1)

    def validate_oval_document(self, file):
        if not oscap_validate_document(file, OSCAP_DOCUMENT_OVAL_DEFINITIONS, None, None, None):
            print "Error: %s not a valid oval definition document" % file
            sys.exit(-1)

    def precallback(self, msg, args):
        result = oscap_reporter_message_get_user2num(msg)
        if result == XCCDF_RESULT_NOT_SELECTED:
            return 0
        print ""
        print "Rule ID: %s" % oscap_reporter_message_get_user1str(msg)
        print "Title: %s" % oscap_reporter_message_get_user3str(msg)
        print "Result:",
        return 0

    def postcallback(self, msg, args):
        result = oscap_reporter_message_get_user2num(msg)
        if result == XCCDF_RESULT_NOT_SELECTED:
            return 0
        print " %s" % xccdf_test_result_type_get_text(result)
        return 0
    
    def evaluate_xccdf(self, file, profile, oval_file):
        self.validate_xccdf_document(file)
        self.validate_oval_document(oval_file)
        self.benchmark = xccdf_benchmark_import(file)
        self.policy_model = xccdf_policy_model_new(self.benchmark)
        self.policy = xccdf_policy_model_get_policy_by_id(self.policy_model, profile)
        if self.policy == None:
            print "Error: No policy to evaluate."
            sys.exit(-1)
        xccdf_policy_model_register_start_callback_py(self.policy_model, self.precallback, None)
        xccdf_policy_model_register_output_callback_py(self.policy_model, self.postcallback, None)
        oval_file = oval_file
        def_model = oval_definition_model_import(oval_file)
        session = oval_agent_new_session(def_model, oval_file)
        xccdf_policy_model_register_engine_oval(self.policy_model, session)
        ritem = xccdf_policy_evaluate(self.policy)
        if ritem == None:
            return OSCAP_EFAMILY_XCCDF
        xccdf_result_set_benchmark_uri(ritem, "testresults")
        title = oscap_text_new()
        oscap_text_set_text(title, "SCAP Scan Result")
        xccdf_result_add_title(ritem, title)
        if self.policy != None:
            sid = xccdf_policy_get_id(self.policy)
            if sid != None:
                xccdf_result_set_profile(ritem, sid)
        oval_agent_export_sysinfo_to_xccdf_result(session, ritem)
        model_iter = xccdf_benchmark_get_models(self.benchmark)
        while xccdf_model_iterator_has_more(model_iter):
            model = xccdf_model_iterator_next(model_iter)
            score = xccdf_policy_get_score(self.policy, ritem, xccdf_model_get_system(model))
            xccdf_result_add_score(ritem, score)
        xccdf_model_iterator_free(model_iter)

        xccdf_benchmark_add_result(self.benchmark, xccdf_result_clone(ritem))
        xccdf_benchmark_export(self.benchmark, "resultsfile")
        oscap_apply_xslt("resultsfile", "xccdf-results-report.xsl", "reportfile", None)#  dict({"oscap-version" : oscap_get_version(), "pwd" : os.path.realpath('.')}))

        res_model = oval_agent_get_results_model(session)
        name = oval_agent_get_filename(session)
        res_direct = oval_result_directives_new(res_model)
        oval_result_directives_set_reported(res_direct, OVAL_RESULT_TRUE | OVAL_RESULT_FALSE |
                                            OVAL_RESULT_UNKNOWN | OVAL_RESULT_NOT_EVALUATED |
                                            OVAL_RESULT_ERROR | OVAL_RESULT_NOT_APPLICABLE, True)
        
        oval_result_directives_set_content(res_direct, OVAL_RESULT_TRUE |
                                           OVAL_RESULT_FALSE |
                                           OVAL_RESULT_UNKNOWN |
                                           OVAL_RESULT_NOT_EVALUATED |
                                           OVAL_RESULT_NOT_APPLICABLE |
                                           OVAL_RESULT_ERROR,
                                           OVAL_DIRECTIVE_CONTENT_FULL)

        oval_results_model_export(res_model, res_direct, name)
        oval_result_directives_free(res_direct)
        
	res_it = xccdf_result_get_rule_results(ritem)
        while xccdf_rule_result_iterator_has_more(res_it):
            res = xccdf_rule_result_iterator_next(res_it)
            result = xccdf_rule_result_get_result(res)
            if result == XCCDF_RESULT_FAIL or result == XCCDF_RESULT_UNKNOWN:
                retval = OSCAP_FAIL
	xccdf_rule_result_iterator_free(res_it)
        oval_definition_model_free(def_model)
        oval_agent_destroy_session(session)
       	xccdf_policy_model_free(self.policy_model)
	oscap_cleanup()


if __name__ == '__main__':
    scanner = XCCDF_Scanner()
    scanner.evaluate_xccdf(sys.argv[1], sys.argv[2], sys.argv[3])
