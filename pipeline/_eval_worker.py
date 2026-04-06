import multiprocessing as mp
import traceback
from typing import List, Optional

def _eval_worker_process(
    story_root: str,
    aspects: Optional[List[str]],
    branch: str,
    save_report: bool,
    result_queue: mp.Queue
) -> None:
    try:
        from evaluation.main import EvaluatorConfig, _create_evaluator, evaluate_story_directory
        from utils import force_cleanup_models

        config = EvaluatorConfig.from_env()
        evaluator = _create_evaluator(config)
        
        result = evaluate_story_directory(
            story_root,
            aspects=aspects,
            branch=branch,
            evaluator=evaluator,
            save_report=save_report
        )
        
        # Attempt to release models aggressively inside this subprocess before returning
        try:
            evaluator._release_all_models()
        except:
            pass
        del evaluator
        force_cleanup_models()

        result_queue.put((result, None))
    except Exception as exc:
        result_queue.put((None, "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))))
