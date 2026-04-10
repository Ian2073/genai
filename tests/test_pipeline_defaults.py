import unittest

from pipeline.entry import resolve_options_from_args
from pipeline.options import DEFAULT_CHIEF_OPTIONS, build_arg_parser


class PipelineDefaultsTests(unittest.TestCase):
    def test_parser_pre_eval_defaults_match_options(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args([])
        self.assertEqual(args.pre_eval_policy, DEFAULT_CHIEF_OPTIONS.pre_eval_policy)
        self.assertEqual(args.pre_eval_threshold, DEFAULT_CHIEF_OPTIONS.pre_eval_threshold)

    def test_resolve_options_uses_candidate_flags(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args(["--outline-candidates", "3", "--title-candidates", "2"])
        options = resolve_options_from_args(args)
        self.assertEqual(options.story_outline_candidates, 3)
        self.assertEqual(options.story_title_candidates, 2)


if __name__ == "__main__":
    unittest.main()
