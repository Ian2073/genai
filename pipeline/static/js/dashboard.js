const STORE_KEY = 'genai.dashboard.form.v4';
    const LANG_STORE_KEY = 'genai.dashboard.lang.v1';
  const MODULE_HIDDEN_JOBS_KEY = 'genai.dashboard.modules.hidden_jobs.v1';

    const I18N = {
      'en': {
        'title.dashboard': 'GenAI Chief Control Plane',
        'hero.eyebrow': 'GenAI Operations',
        'hero.title': 'Chief Control Plane',
        'hero.sub': 'Operate runs, inspect alerts, manage queue priority, and audit production history from one dashboard.',
        'label.auto_refresh': 'Auto refresh',
        'label.language': 'Language',
        'kpi.system_state': 'System State',
        'kpi.queue_depth': 'Queue Depth',
        'kpi.success_rate': 'Success Rate',
        'kpi.avg_duration': 'Avg Duration',
        'kpi.gpu_cost': 'Est. GPU Cost',
        'tab.overview': 'Generate',
        'tab.ops': 'Operations',
        'tab.detail': 'Run Detail',
        'tab.evaluation': 'Evaluation',
        'tab.modules': 'Modules',
        'label.tab_gallery': 'Gallery',
        'gallery.title': 'Story Gallery',
        'gallery.sub': 'Browse generated stories with cover previews and quick metadata.',
        'gallery.system_title': 'System Snapshot',
        'gallery.system_hint': 'Live resource usage helps avoid running heavy stages under memory pressure.',
        'gallery.system.gpu_na': 'GPU: n/a',
        'gallery.system.status': 'RAM: {ram}% | {gpu}',
        'gallery.system.gpu_na': 'GPU: n/a',
        'gallery.system.status': 'RAM: {ram}% | {gpu}',
        'overview.composer.title': 'Run Composer',
        'overview.composer.sub': 'Product mode supports queueing with priority and versioned run profiles.',
        'overview.telemetry.title': 'Live Telemetry',
        'overview.field.book_count': 'Book Count',
        'overview.field.retry_per_book': 'Retry Per Book',
        'overview.field.queue_priority': 'Queue Priority',
        'overview.field.age': 'Age',
        'overview.field.category': 'Category',
        'overview.field.theme_preset': 'Theme (preset)',
        'overview.field.subcategory_preset': 'Subcategory (preset)',
        'overview.field.story_input_mode': 'Story Input Mode',
        'overview.field.speaker_wav_optional': 'Speaker WAV (optional)',
        'overview.field.theme_custom': 'Theme (custom)',
        'overview.field.subcategory_custom': 'Subcategory (custom)',
        'overview.field.pages_auto': 'Pages (0 = auto)',
        'overview.field.seed_auto': 'Seed (empty = auto)',
        'overview.field.story_prompt_free': 'Story Prompt (free text)',
        'overview.field.materials_elements': 'Materials / Elements',
        'overview.field.speaker_dir_optional': 'Speaker Samples Dir (optional)',
        'overview.field.recording_script_recommended': 'Recording Script (recommended)',
        'overview.field.config_version_name': 'Config Version Name',
        'overview.field.version_note': 'Version Note',
        'overview.toggle.photo': 'Photo',
        'overview.toggle.translation': 'Translation',
        'overview.toggle.voice': 'Voice',
        'overview.toggle.verify': 'Verify',
        'overview.toggle.low_vram': 'Low VRAM',
        'overview.toggle.strict_translation': 'Strict translation',
        'overview.toggle.strict_voice': 'Strict voice',
        'overview.preset.balanced': 'Balanced',
        'overview.preset.speed': 'Speed',
        'overview.preset.quality': 'Quality',
        'overview.metric.total': 'Total',
        'overview.metric.completed': 'Completed',
        'overview.metric.success': 'Success',
        'overview.metric.failed': 'Failed',
        'overview.metric.elapsed': 'Elapsed',
        'overview.metric.eta': 'ETA',
        'overview.progress.detail': '{done}/{total} completed | {remaining} remaining',
        'overview.progress.books': 'Books {done}/{total}',
        'overview.progress.remaining': 'Remaining {count}',
        'overview.progress.success_rate': 'Success {pct}%',
        'overview.progress.stage': 'Stage {stage}',
        'overview.logs.title': 'Live Logs (Now)',
        'overview.logs.hint': 'Latest lines from the active run. Full logs are in Run Detail.',
        'overview.meta.run_id': 'Run ID',
        'overview.meta.pid': 'PID',
        'overview.meta.exit_code': 'Exit Code',
        'overview.meta.queue_depth': 'Queue Depth',
        'ops.queue.title': 'Queue and Priority',
        'ops.alert.title': 'Alert Center',
        'ops.capacity.title': 'Capacity and Cost',
        'ops.capacity.window_runs': 'Window Runs',
        'ops.capacity.success_rate': 'Success Rate',
        'ops.capacity.books_per_hour': 'Books / Hour',
        'ops.capacity.avg_queue_delay': 'Avg Queue Delay',
        'ops.capacity.gpu_hours': 'GPU Hours',
        'ops.capacity.gpu_cost': 'GPU Cost',
        'ops.config.title': 'Config Versions',
        'ops.logs.title': 'Live Logs',
        'ops.recent.title': 'Recent Runs',
        'detail.selector.title': 'Run Detail Selector',
        'detail.summary.title': 'Run Summary',
        'detail.summary.state': 'State',
        'detail.summary.duration': 'Duration',
        'detail.summary.exit_code': 'Exit Code',
        'detail.summary.total_books': 'Total Books',
        'detail.summary.success_books': 'Success Books',
        'detail.summary.failed_books': 'Failed Books',
        'detail.summary.priority': 'Priority',
        'detail.summary.queue_delay': 'Queue Delay',
        'detail.summary.started_at': 'Started At',
        'detail.summary.finished_at': 'Finished At',
        'detail.book': 'Book',
        'detail.timeline.title': 'Timeline and Alerts',
        'detail.related_alerts.title': 'Related Alerts',
        'detail.logs.title': 'Run Logs',
        'eval.title': 'Evaluation Diagnostics',
        'eval.sub': 'Inspect assessment reports by latest story, run ID, or manual story root.',
        'eval.source': 'Data Source',
        'eval.source.latest': 'Latest Story',
        'eval.source.run': 'Run ID',
        'eval.source.story_root': 'Story Root',
        'eval.run_id': 'Run ID',
        'eval.book': 'Book',
        'eval.book.latest': 'Latest book',
        'eval.story_root': 'Story Root',
        'eval.branch': 'Branch',
        'eval.overall': 'Overall Score',
        'eval.scope': 'Scope',
        'eval.branch_used': 'Branch',
        'eval.report_file': 'Report File',
        'eval.meta.source': 'Source',
        'eval.meta.run_id': 'Run ID',
        'eval.meta.story_root': 'Story Root',
        'eval.chart.title': 'Dimension Radar',
        'eval.log.title': 'Assessment JSON',
        'module.jobs.title': 'Module Jobs',
        'module.job_detail.title': 'Module Job Detail',
        'module.job_events.title': 'Events',
        'module.job_logs.title': 'Logs',
        'module.workbenches.title': 'Module Workbenches',
        'module.workbenches.sub': 'Run text, image, translation, and voice independently without executing the full pipeline.',
        'module.tab.story': 'Text Studio',
        'module.tab.image': 'Image Studio',
        'module.tab.translation': 'Translation Studio',
        'module.tab.voice': 'Voice Studio',
        'module.tab.general': 'General Studio',
        'general.tools.title': 'General AI Toolkit',
        'general.tools.sub': 'Use direct non-story tools for text QA, image generation, translation, and TTS preview.',
        'module.story.book_count': 'Book Count',
        'module.story.pages_auto': 'Pages (0 = auto)',
        'module.story.priority': 'Priority',
        'module.story.age': 'Age',
        'module.story.category': 'Category',
        'module.story.input_mode': 'Input Mode',
        'module.story.theme_preset': 'Theme (preset)',
        'module.story.subcategory_preset': 'Subcategory (preset)',
        'module.story.theme_custom': 'Theme (custom)',
        'module.story.subcategory_custom': 'Subcategory (custom)',
        'module.story.seed_optional': 'Seed (optional)',
        'module.story.low_vram': 'Low VRAM',
        'module.story.prompt_custom': 'Story Prompt (custom mode)',
        'module.story.materials_custom': 'Story Materials (custom mode)',
        'module.image.job_priority': 'Module Job Priority',
        'module.image.width': 'Width',
        'module.image.height': 'Height',
        'module.image.steps': 'Steps',
        'module.image.guidance': 'Guidance',
        'module.image.seed': 'Seed',
        'module.image.refiner_steps': 'Refiner Steps',
        'module.image.skip_refiner': 'Skip refiner',
        'module.translation.story_root_optional': 'Story Root (optional, auto-filled)',
        'module.translation.story_select': 'Story Book (auto detected)',
        'module.translation.priority': 'Priority',
        'module.translation.source_folder': 'Source Folder',
        'module.translation.source_lang_code': 'Source Language Code',
        'module.translation.beam_size': 'Beam Size',
        'module.translation.length_penalty': 'Length Penalty',
        'module.translation.device': 'Device',
        'module.translation.dtype': 'DType',
        'module.translation.target_languages': 'Target Languages (multi-select)',
        'module.translation.refresh_story_list': 'Refresh Story List',
        'module.translation.story_select_placeholder': '-- Select a story book --',
        'module.translation.story_count': 'Detected stories: {count}',
        'module.translation.story_no_available': 'No translatable story found.',
        'module.translation.story_selected_meta': 'Languages: {languages} | Updated: {updated}',
        'module.translation.lang.zh': 'Chinese (zh)',
        'module.translation.lang.ja': 'Japanese (ja)',
        'module.translation.lang.ko': 'Korean (ko)',
        'module.translation.lang.en': 'English (en)',
        'module.translation.lang.fr': 'French (fr)',
        'module.translation.lang.de': 'German (de)',
        'module.translation.lang.es': 'Spanish (es)',
        'module.translation.lang.pt': 'Portuguese (pt)',
        'module.translation.code.eng_latn': 'English (eng_Latn)',
        'module.translation.code.zho_hant': 'Traditional Chinese (zho_Hant)',
        'module.translation.code.zho_hans': 'Simplified Chinese (zho_Hans)',
        'module.translation.code.jpn_jpan': 'Japanese (jpn_Jpan)',
        'module.translation.code.kor_hang': 'Korean (kor_Hang)',
        'module.translation.code.fra_latn': 'French (fra_Latn)',
        'module.translation.code.deu_latn': 'German (deu_Latn)',
        'module.translation.code.spa_latn': 'Spanish (spa_Latn)',
        'module.translation.code.por_latn': 'Portuguese (por_Latn)',
        'module.voice.story_root_optional': 'Story Root (optional)',
        'module.voice.language_auto': 'Language (blank = auto detect)',
        'module.voice.speaker_wav_optional': 'Speaker WAV (optional)',
        'module.voice.speaker_dir_optional': 'Speaker Dir (optional)',
        'module.voice.record_hint': 'Record a speaker sample directly in Voice Studio and save it to Speaker WAV.',
        'module.voice.record_script_optional': 'Recording Script (optional)',
        'module.voice.page_start_optional': 'Page Start (optional)',
        'module.voice.page_end_optional': 'Page End (optional)',
        'module.voice.priority': 'Priority',
        'module.voice.gain': 'Gain',
        'module.voice.speed': 'Speed',
        'module.voice.device': 'Device',
        'module.voice.concat_full_narration': 'Concat full narration',
        'module.voice.keep_raw_files': 'Keep raw files',
        'module.option.auto': 'Auto',
        'module.priority.high': 'high',
        'module.priority.normal': 'normal',
        'module.priority.low': 'low',
        'module.category.adventure': 'adventure',
        'module.category.educational': 'educational',
        'module.category.fun': 'fun',
        'module.category.cultural': 'cultural',
        'module.theme.friendship': 'friendship',
        'module.theme.courage': 'courage',
        'module.theme.mystery': 'mystery',
        'module.theme.family': 'family',
        'module.theme.animals': 'animals',
        'module.subcategory.forest': 'forest',
        'module.subcategory.tradition': 'tradition',
        'module.subcategory.science': 'science',
        'module.subcategory.magic': 'magic',
        'module.subcategory.holiday': 'holiday',
        'module.placeholder.optional': 'optional',
        'module.placeholder.story_root': 'output/.../story_name',
        'module.placeholder.source_lang': 'eng_Latn',
        'module.placeholder.target_langs': 'zh\nja\nko',
        'module.placeholder.language': 'en',
        'module.placeholder.speaker_wav': 'runs/voice_samples/speaker-xxx.wav',
        'module.placeholder.speaker_dir': 'models/XTTS-v2/samples',
        'module.general.section.text': 'General Text',
        'module.general.section.image': 'General Image',
        'module.general.section.translation': 'General Translation',
        'module.general.section.voice': 'General Voice (TTS)',
        'module.general.text.prompt': 'Prompt',
        'module.general.text.system_instruction': 'System Instruction',
        'module.general.text.max_tokens': 'Max Tokens',
        'module.general.text.temperature': 'Temperature',
        'module.general.text.top_p': 'Top P',
        'module.general.text.top_k': 'Top K',
        'module.general.text.meta_empty': 'No text result yet.',
        'module.general.text.output_empty': 'No text result yet.',
        'module.general.text.meta': 'tokens={tokens} | model={model}',
        'module.general.image.prompt': 'Prompt',
        'module.general.image.negative_prompt': 'Negative Prompt',
        'module.general.image.width': 'Width',
        'module.general.image.height': 'Height',
        'module.general.image.steps': 'Steps',
        'module.general.image.guidance': 'Guidance',
        'module.general.image.seed_optional': 'Seed (optional)',
        'module.general.image.refiner_steps_optional': 'Refiner Steps (optional)',
        'module.general.image.skip_refiner': 'Skip Refiner',
        'module.general.image.low_vram': 'Low VRAM',
        'module.general.image.meta_empty': 'No image generated yet.',
        'module.general.image.meta': 'path={path} | seed={seed} | {width}x{height}',
        'module.general.translation.input_text': 'Input Text',
        'module.general.translation.source_language': 'Source Language',
        'module.general.translation.target_language': 'Target Language',
        'module.general.translation.beam_size': 'Beam Size',
        'module.general.translation.dtype': 'DType',
        'module.general.translation.meta_empty': 'No translation yet.',
        'module.general.translation.meta': 'source={source} -> target={target}',
        'module.general.voice.narration_text': 'Narration Text',
        'module.general.voice.language': 'Language',
        'module.general.voice.speaker_wav_optional': 'Speaker WAV (optional)',
        'module.general.voice.speed': 'Speed',
        'module.general.voice.temperature': 'Temperature',
        'module.general.voice.meta_empty': 'No audio generated yet.',
        'module.general.voice.meta': 'audio={audio} | speaker={speaker}',
        'module.general.placeholder.text_prompt': 'Ask a question or describe a task',
        'module.general.placeholder.image_prompt': 'Describe the image you want',
        'module.general.placeholder.image_negative': 'Optional negative prompt',
        'module.general.placeholder.translation_input': 'Paste text to translate',
        'module.general.placeholder.voice_text': 'Type text to synthesize',
        'module.general.placeholder.voice_speaker_wav': 'runs/voice_samples/speaker-xxx.wav',
        'image.live_preview.title': 'Live Image Preview',
        'image.hint': 'Select one image to inspect original prompt and parameters, then regenerate with edits.',
        'image.selected': 'Selected Image',
        'image.positive': 'Positive Prompt',
        'image.negative': 'Negative Prompt',
        'btn.refresh_now': 'Refresh now',
        'btn.save_template': 'Save Template',
        'btn.gallery_refresh': 'Refresh Gallery',
        'btn.start': 'Start / Queue',
        'btn.stop': 'Stop Active',
        'btn.save_local': 'Save Local',
        'btn.load_local': 'Load Local',
        'btn.save_version': 'Save Config Version',
        'btn.record_start': 'Start Recording',
        'btn.record_stop': 'Stop Recording',
        'btn.record_save': 'Save As Speaker WAV',
        'btn.detail': 'Detail',
        'btn.stop_short': 'Stop',
        'btn.clear': 'Clear',
        'btn.clear_view': 'Clear View',
        'btn.clear_module_view': 'Clear View',
        'btn.show_all': 'Show All',
        'btn.clear_history': 'Clear Ops History',
        'btn.refresh_detail': 'Refresh Detail',
        'btn.refresh_jobs': 'Refresh Jobs',
        'btn.refresh_evaluation': 'Refresh Evaluation',
        'btn.stop_selected': 'Stop Selected',
        'btn.refresh_images': 'Refresh Images',
        'btn.refresh_story_list': 'Refresh Story List',
        'btn.regen_selected': 'Regenerate Selected',
        'btn.queue_image_module': 'Queue Image Module Job',
        'btn.regen_with_edits': 'Regenerate This (With Edits)',
        'btn.run_text_module': 'Run Text Module',
        'btn.run_translation_module': 'Run Translation Module',
        'btn.run_voice_module': 'Run Voice Module',
        'btn.run_general_text': 'Run General Text',
        'btn.run_general_image': 'Run General Image',
        'btn.run_general_translation': 'Run General Translation',
        'btn.run_general_voice': 'Run General Voice',
        'btn.apply': 'Apply',
        'btn.cancel': 'Cancel',
        'btn.acknowledge': 'Acknowledge',
        'btn.inspect': 'Inspect',
        'btn.select': 'Select',
        'th.job': 'Job',
        'th.state': 'State',
        'th.priority': 'Priority',
        'th.books': 'Books',
        'th.category': 'Category',
        'th.age': 'Age',
        'th.action': 'Action',
        'th.version': 'Version',
        'th.created': 'Created',
        'th.note': 'Note',
        'th.usage': 'Usage',
        'th.run': 'Run',
        'th.started': 'Started',
        'th.duration': 'Duration',
        'th.result': 'Result',
        'th.config': 'Config',
        'th.type': 'Type',
        'th.status': 'Status',
        'th.story_root': 'Story Root',
        'msg.request_failed': 'Request failed',
        'msg.refresh_failed': 'Refresh failed.',
        'msg.select_module_job_first': 'Select a module job first.',
        'msg.no_module_jobs': 'No module jobs.',
        'msg.no_module_job_selected': 'No module job selected.',
        'msg.no_events': 'No events.',
        'msg.no_module_logs': 'No module logs.',
        'msg.submitting_module_job': 'Submitting module job...',
        'msg.module_job_queued': 'Module job queued: {id}',
        'msg.failed_run_module_job': 'Failed to run module job.',
        'msg.translation_targets_required': 'Please select at least one target language.',
        'msg.loading_story_list': 'Loading available story books...',
        'msg.story_list_load_failed': 'Failed to load story list.',
        'msg.stop_requested_for_module_job': 'Stop requested for module job {id}',
        'msg.failed_stop_module_job': 'Failed to stop module job.',
        'msg.none_selected': 'None selected.',
        'msg.no_live_logs': 'No active run logs yet.',
        'msg.no_generated_images': 'No generated images yet.',
        'msg.select_at_least_one_image': 'Please select at least one image item.',
        'msg.regenerating_selected_images': 'Regenerating selected images...',
        'msg.regenerated_images': 'Regenerated {ok}/{total} images.',
        'msg.failed_regenerate_selected_images': 'Failed to regenerate selected images.',
        'msg.select_image_for_regen': 'Select one image to regenerate with edits.',
        'msg.regenerating_image_with_edits': 'Regenerating selected image with edited parameters...',
        'msg.image_regenerated_successfully': 'Image regenerated successfully.',
        'msg.image_regeneration_failed': 'Image regeneration failed.',
        'msg.failed_regenerate_image': 'Failed to regenerate image.',
        'msg.recording_read_script': 'Recording... please read the script naturally.',
        'msg.microphone_access_failed': 'Microphone access failed.',
        'msg.recording_captured': 'Recording captured. You can preview and save it as speaker WAV.',
        'msg.no_recording_available': 'No recording available.',
        'msg.speaker_sample_saved': 'Speaker sample saved: {path}',
        'msg.failed_save_recording': 'Failed to save recording.',
        'msg.saved_local_profile': 'Saved local form profile.',
        'msg.preset_applied': 'Preset applied: {name}',
        'msg.no_run_history': 'No run history yet.',
        'confirm.clear_overview_view': 'Clear live overview panel data only? Operations history will be kept.',
        'msg.clearing_overview_view': 'Clearing overview panel...',
        'msg.cleared_overview_view': 'Overview panel cleared ({count} live lines).',
        'msg.failed_clear_overview_view': 'Failed to clear overview panel.',
        'confirm.clear_run_history': 'Clear all run history records and related logs?',
        'msg.clearing_run_history': 'Clearing run history...',
        'msg.cleared_run_history': 'Run history cleared ({count} items).',
        'msg.clear_history_blocked_running': 'Stop active and queued runs before clearing history.',
        'msg.failed_clear_run_history': 'Failed to clear run history.',
        'msg.cleared_module_view': 'Module panel cleared ({count} records hidden).',
        'msg.module_view_restored': 'Module panel restored to show all records.',
        'msg.module_view_already_clean': 'Module panel is already clear.',
        'msg.no_runs_available': 'No runs available',
        'msg.eval_loading': 'Loading evaluation report...',
        'msg.eval_no_data': 'No evaluation loaded.',
        'msg.eval_no_dimensions': 'No dimension score found in this report.',
        'msg.eval_run_required': 'Please select a run ID first.',
        'msg.eval_no_books': 'No books found in this run.',
        'msg.eval_story_root_required': 'Please enter story_root first.',
        'msg.eval_fetch_failed': 'Failed to load evaluation report.',
        'msg.queue_empty': 'Queue is empty.',
        'msg.no_alerts': 'No alerts.',
        'msg.no_trend_data': 'No trend data yet.',
        'msg.no_saved_versions': 'No saved versions.',
        'msg.no_related_alerts': 'No related alerts.',
        'msg.no_run_logs': 'No run logs.',
        'msg.no_images_found': 'No images found.',
        'msg.general_prompt_required': 'Please enter a prompt.',
        'msg.general_text_required': 'Please enter text.',
        'msg.general_voice_text_required': 'Please enter narration text.',
        'msg.general_running': 'Running request...',
        'msg.general_text_done': 'General text generation completed.',
        'msg.general_image_done': 'General image generation completed.',
        'msg.general_translation_done': 'General translation completed.',
        'msg.general_voice_done': 'General voice generation completed.',
        'msg.general_request_failed': 'General request failed.',
        'msg.general_already_running': 'A request is still running. Please wait.',
        'msg.prompt_empty': 'Prompt is empty.',
        'msg.template_name_required': 'Please enter a template name first.',
        'msg.book_count_min': 'Book count must be >= 1.',
        'msg.submitting_run_request': 'Submitting run request...',
        'msg.run_started': 'Run started: {id}',
        'msg.run_queued': 'Run queued at position {pos}.',
        'msg.failed_start_run': 'Failed to start run.',
        'msg.stopping_active_run': 'Stopping active run...',
        'msg.stopped_and_started_next': 'Stopped current run and started next queued run.',
        'msg.stopped': 'Stopped.',
        'msg.failed_stop_run': 'Failed to stop run.',
        'msg.saved_config_version': 'Saved config version: {id}',
        'msg.failed_save_config_version': 'Failed to save config version.',
        'msg.applied_config_version': 'Applied config version: {id}',
        'msg.failed_apply_config_version': 'Failed to apply config version.',
        'msg.updated_priority': 'Updated priority for job {id}.',
        'msg.failed_reprioritize_job': 'Failed to reprioritize job.',
        'msg.canceled_job': 'Canceled queued job {id}.',
        'msg.failed_cancel_job': 'Failed to cancel job.',
        'msg.failed_ack_alert': 'Failed to acknowledge alert.',
        'msg.loaded_local_profile': 'Loaded local profile.',
        'msg.saving_template': 'Saving template...',
        'msg.template_saved': 'Template saved.',
        'msg.template_save_failed': 'Failed to save template.',
        'msg.template_loaded': 'Template loaded.',
        'meta.book': 'book',
        'meta.stage': 'stage',
        'meta.updated': 'updated',
        'meta.count': 'count',
        'meta.retry': 'retry',
        'meta.category': 'category',
        'meta.age': 'age',
        'module.meta.job': 'Job',
        'module.meta.type': 'Type',
        'module.meta.status': 'Status',
        'module.meta.priority': 'Priority',
        'module.meta.image_selected': 'Task={task} | Type={type} | Story={story}',
        'state.idle': 'idle',
        'state.running': 'running',
        'state.completed': 'completed',
        'state.failed': 'failed',
        'state.stopped': 'stopped',
        'state.queued': 'queued',
        'state.error': 'error',
        'state.active': 'active',
        'placeholder.theme': 'ex: friendship, courage, mystery',
        'placeholder.subcategory': 'ex: forest, tradition, science',
        'placeholder.seed': 'auto',
        'placeholder.story_prompt': 'Describe style, plot direction, constraints, or desired emotional arc.',
        'placeholder.story_materials': 'One line per item, e.g.\nmagic map\nold tree\nrainy night',
        'placeholder.story_prompt_preset': 'Preset mode: direct generation (no conversion layer).',
        'placeholder.story_materials_preset': 'Preset mode: direct generation (no conversion layer).',
        'placeholder.story_prompt_custom': 'Use concise requirements: mood, values, characters, conflict, ending style.',
        'placeholder.story_materials_custom': 'Paste notes, outlines, facts, classroom material, or family context.',
        'placeholder.speaker_wav': 'ex: models/XTTS-v2/samples/my_parent.wav',
        'placeholder.theme_custom': 'ex: friendship, courage, mystery',
        'placeholder.subcategory_custom': 'ex: forest, tradition, science',
        'placeholder.speaker_dir': 'ex: models/XTTS-v2/samples/custom',
        'placeholder.version_name': 'example: quality-v3',
        'placeholder.version_note': 'what changed and why',
        'placeholder.template_name': 'Template name',
        'template.placeholder': '-- Load a template --',
        'prompt.template_name': 'Enter a template name:',
        'prompt.template_default_name': 'Story Template',
        'option.lang.zh_tw': 'Traditional Chinese',
        'option.lang.en': 'English',
        'option.story_input_mode.preset': 'preset (use KG defaults)',
        'option.story_input_mode.custom': 'custom (convert user input)',
        'option.module_story_input_mode.preset': 'preset',
        'option.module_story_input_mode.custom': 'custom',
      },
      'zh-TW': {
        'title.dashboard': 'GenAI 故事生成控制台',
        'hero.eyebrow': 'GenAI 營運面板',
        'hero.title': '故事生成總控台',
        'hero.sub': '在同一個儀表板管理生成任務、監看警示、調整佇列優先序，並追蹤執行歷史。',
        'label.auto_refresh': '自動刷新',
        'label.language': '語言',
        'kpi.system_state': '系統狀態',
        'kpi.queue_depth': '佇列深度',
        'kpi.success_rate': '成功率',
        'kpi.avg_duration': '平均耗時',
        'kpi.gpu_cost': '預估 GPU 成本',
        'tab.overview': '故事生成',
        'tab.ops': '營運中心',
        'tab.detail': '執行明細',
        'tab.evaluation': '評估診斷',
        'tab.modules': '模組工作台',
        'label.tab_gallery': '作品圖庫',
        'gallery.title': '故事圖庫',
        'gallery.sub': '快速瀏覽已產生故事、封面預覽與基本資訊。',
        'gallery.system_title': '系統資源快照',
        'gallery.system_hint': '即時資源監看可避免在記憶體壓力過高時啟動重型流程。',
        'gallery.system.gpu_na': 'GPU：無資料',
        'gallery.system.status': 'RAM：{ram}% | {gpu}',
        'gallery.system.gpu_na': 'GPU：無資料',
        'gallery.system.status': 'RAM：{ram}% | {gpu}',
        'overview.composer.title': '主流程生成設定',
        'overview.composer.sub': '主介面用於一般故事生成流程，支援排隊、優先序與版本化設定。',
        'overview.telemetry.title': '即時執行監控',
        'overview.field.book_count': '生成本數',
        'overview.field.retry_per_book': '每本重試次數',
        'overview.field.queue_priority': '佇列優先序',
        'overview.field.age': '年齡層',
        'overview.field.category': '類別',
        'overview.field.theme_preset': '主題（預設）',
        'overview.field.subcategory_preset': '子類別（預設）',
        'overview.field.story_input_mode': '故事輸入模式',
        'overview.field.speaker_wav_optional': 'Speaker WAV（選填）',
        'overview.field.theme_custom': '主題（自訂）',
        'overview.field.subcategory_custom': '子類別（自訂）',
        'overview.field.pages_auto': '頁數（0 代表自動）',
        'overview.field.seed_auto': 'Seed（留空 = 自動）',
        'overview.field.story_prompt_free': '故事提示（自由文字）',
        'overview.field.materials_elements': '素材 / 元素',
        'overview.field.speaker_dir_optional': '說話人樣本資料夾（選填）',
        'overview.field.recording_script_recommended': '錄音稿（建議）',
        'overview.field.config_version_name': '設定版本名稱',
        'overview.field.version_note': '版本備註',
        'overview.toggle.photo': '圖片',
        'overview.toggle.translation': '翻譯',
        'overview.toggle.voice': '語音',
        'overview.toggle.verify': '驗證',
        'overview.toggle.low_vram': '低 VRAM',
        'overview.toggle.strict_translation': '嚴格翻譯',
        'overview.toggle.strict_voice': '嚴格語音',
        'overview.preset.balanced': '平衡',
        'overview.preset.speed': '速度',
        'overview.preset.quality': '品質',
        'overview.metric.total': '總數',
        'overview.metric.completed': '已完成',
        'overview.metric.success': '成功',
        'overview.metric.failed': '失敗',
        'overview.metric.elapsed': '已耗時',
        'overview.metric.eta': '預估剩餘',
        'overview.progress.detail': '已完成 {done}/{total} | 剩餘 {remaining}',
        'overview.progress.books': '書本進度 {done}/{total}',
        'overview.progress.remaining': '剩餘 {count}',
        'overview.progress.success_rate': '成功率 {pct}%',
        'overview.progress.stage': '階段 {stage}',
        'overview.logs.title': '即時日誌（主畫面）',
        'overview.logs.hint': '顯示目前執行的最新日誌；完整日誌可到執行明細查看。',
        'overview.meta.run_id': 'Run ID',
        'overview.meta.pid': 'PID',
        'overview.meta.exit_code': '結束代碼',
        'overview.meta.queue_depth': '佇列深度',
        'ops.queue.title': '佇列與優先序',
        'ops.alert.title': '警示中心',
        'ops.capacity.title': '容量與成本',
        'ops.capacity.window_runs': '視窗內任務數',
        'ops.capacity.success_rate': '成功率',
        'ops.capacity.books_per_hour': '每小時書本數',
        'ops.capacity.avg_queue_delay': '平均排隊延遲',
        'ops.capacity.gpu_hours': 'GPU 時數',
        'ops.capacity.gpu_cost': 'GPU 成本',
        'ops.config.title': '設定版本庫',
        'ops.logs.title': '即時日誌',
        'ops.recent.title': '近期執行紀錄',
        'detail.selector.title': '執行明細選擇器',
        'detail.summary.title': '執行摘要',
        'detail.summary.state': '狀態',
        'detail.summary.duration': '耗時',
        'detail.summary.exit_code': '結束代碼',
        'detail.summary.total_books': '總書本數',
        'detail.summary.success_books': '成功書本數',
        'detail.summary.failed_books': '失敗書本數',
        'detail.summary.priority': '優先序',
        'detail.summary.queue_delay': '排隊延遲',
        'detail.summary.started_at': '開始時間',
        'detail.summary.finished_at': '完成時間',
        'detail.book': '書本',
        'detail.timeline.title': '時間線與警示',
        'detail.related_alerts.title': '相關警示',
        'detail.logs.title': '執行日誌',
        'eval.title': '評估診斷',
        'eval.sub': '可依最新故事、Run ID 或手動故事路徑檢視評估報告。',
        'eval.source': '資料來源',
        'eval.source.latest': '最新故事',
        'eval.source.run': 'Run ID',
        'eval.source.story_root': '故事路徑',
        'eval.run_id': 'Run ID',
        'eval.book': '書本',
        'eval.book.latest': '最新一本',
        'eval.story_root': '故事路徑',
        'eval.branch': '分支',
        'eval.overall': '總分',
        'eval.scope': '評估範圍',
        'eval.branch_used': '分支',
        'eval.report_file': '報告檔案',
        'eval.meta.source': '來源',
        'eval.meta.run_id': 'Run ID',
        'eval.meta.story_root': '故事路徑',
        'eval.chart.title': '維度雷達圖',
        'eval.log.title': '評估 JSON',
        'module.jobs.title': '模組任務佇列',
        'module.job_detail.title': '模組任務明細',
        'module.job_events.title': '事件',
        'module.job_logs.title': '日誌',
        'module.workbenches.title': '獨立模組工作台',
        'module.workbenches.sub': '文字、圖像、翻譯、語音可分別獨立執行，不必跑完整主流程。',
        'module.tab.story': '文字工作台',
        'module.tab.image': '圖像工作台',
        'module.tab.translation': '翻譯工作台',
        'module.tab.voice': '語音工作台',
        'module.tab.general': '通用工作台',
        'general.tools.title': '通用 AI 工具箱',
        'general.tools.sub': '提供非故事流程的即時工具：文字問答、圖像生成、翻譯與語音試聽。',
        'module.story.book_count': '生成本數',
        'module.story.pages_auto': '頁數（0 代表自動）',
        'module.story.priority': '優先序',
        'module.story.age': '年齡層',
        'module.story.category': '類別',
        'module.story.input_mode': '輸入模式',
        'module.story.theme_preset': '主題（預設）',
        'module.story.subcategory_preset': '子類別（預設）',
        'module.story.theme_custom': '主題（自訂）',
        'module.story.subcategory_custom': '子類別（自訂）',
        'module.story.seed_optional': 'Seed（選填）',
        'module.story.low_vram': '低 VRAM 模式',
        'module.story.prompt_custom': '故事提示（自訂模式）',
        'module.story.materials_custom': '故事素材（自訂模式）',
        'module.image.job_priority': '模組任務優先序',
        'module.image.width': '寬度',
        'module.image.height': '高度',
        'module.image.steps': '步數',
        'module.image.guidance': 'Guidance',
        'module.image.seed': 'Seed',
        'module.image.refiner_steps': 'Refiner 步數',
        'module.image.skip_refiner': '略過 Refiner',
        'module.translation.story_root_optional': '故事路徑（選填，自動帶入）',
        'module.translation.story_select': '故事書（自動偵測）',
        'module.translation.priority': '優先序',
        'module.translation.source_folder': '來源資料夾',
        'module.translation.source_lang_code': '來源語言代碼',
        'module.translation.beam_size': 'Beam 大小',
        'module.translation.length_penalty': 'Length Penalty',
        'module.translation.device': '裝置',
        'module.translation.dtype': 'DType',
        'module.translation.target_languages': '目標語言（可多選）',
        'module.translation.refresh_story_list': '刷新故事清單',
        'module.translation.story_select_placeholder': '-- 請選擇故事書 --',
        'module.translation.story_count': '可翻譯故事數：{count}',
        'module.translation.story_no_available': '目前找不到可翻譯的故事。',
        'module.translation.story_selected_meta': '可用語言：{languages} | 更新：{updated}',
        'module.translation.lang.zh': '中文 (zh)',
        'module.translation.lang.ja': '日文 (ja)',
        'module.translation.lang.ko': '韓文 (ko)',
        'module.translation.lang.en': '英文 (en)',
        'module.translation.lang.fr': '法文 (fr)',
        'module.translation.lang.de': '德文 (de)',
        'module.translation.lang.es': '西文 (es)',
        'module.translation.lang.pt': '葡文 (pt)',
        'module.translation.code.eng_latn': '英文 (eng_Latn)',
        'module.translation.code.zho_hant': '繁中 (zho_Hant)',
        'module.translation.code.zho_hans': '簡中 (zho_Hans)',
        'module.translation.code.jpn_jpan': '日文 (jpn_Jpan)',
        'module.translation.code.kor_hang': '韓文 (kor_Hang)',
        'module.translation.code.fra_latn': '法文 (fra_Latn)',
        'module.translation.code.deu_latn': '德文 (deu_Latn)',
        'module.translation.code.spa_latn': '西文 (spa_Latn)',
        'module.translation.code.por_latn': '葡文 (por_Latn)',
        'module.voice.story_root_optional': '故事路徑（選填）',
        'module.voice.language_auto': '語言（留空 = 自動偵測）',
        'module.voice.speaker_wav_optional': 'Speaker WAV（選填）',
        'module.voice.speaker_dir_optional': 'Speaker 資料夾（選填）',
        'module.voice.record_hint': '可直接在語音工作台錄製說話人樣本，並儲存到 Speaker WAV。',
        'module.voice.record_script_optional': '錄音腳本（選填）',
        'module.voice.page_start_optional': '起始頁（選填）',
        'module.voice.page_end_optional': '結束頁（選填）',
        'module.voice.priority': '優先序',
        'module.voice.gain': '音量增益',
        'module.voice.speed': '語速',
        'module.voice.device': '裝置',
        'module.voice.concat_full_narration': '合併完整旁白',
        'module.voice.keep_raw_files': '保留原始檔案',
        'module.option.auto': '自動',
        'module.priority.high': '高',
        'module.priority.normal': '一般',
        'module.priority.low': '低',
        'module.category.adventure': '冒險',
        'module.category.educational': '教育',
        'module.category.fun': '趣味',
        'module.category.cultural': '文化',
        'module.theme.friendship': '友情',
        'module.theme.courage': '勇氣',
        'module.theme.mystery': '神祕',
        'module.theme.family': '家庭',
        'module.theme.animals': '動物',
        'module.subcategory.forest': '森林',
        'module.subcategory.tradition': '傳統',
        'module.subcategory.science': '科學',
        'module.subcategory.magic': '魔法',
        'module.subcategory.holiday': '節日',
        'module.placeholder.optional': '選填',
        'module.placeholder.story_root': 'output/.../story_name',
        'module.placeholder.source_lang': 'eng_Latn',
        'module.placeholder.target_langs': 'zh\nja\nko',
        'module.placeholder.language': 'en',
        'module.placeholder.speaker_wav': 'runs/voice_samples/speaker-xxx.wav',
        'module.placeholder.speaker_dir': 'models/XTTS-v2/samples',
        'module.general.section.text': '通用文字',
        'module.general.section.image': '通用圖像',
        'module.general.section.translation': '通用翻譯',
        'module.general.section.voice': '通用語音（TTS）',
        'module.general.text.prompt': '提示詞',
        'module.general.text.system_instruction': '系統指令',
        'module.general.text.max_tokens': '最大 Tokens',
        'module.general.text.temperature': '溫度',
        'module.general.text.top_p': 'Top P',
        'module.general.text.top_k': 'Top K',
        'module.general.text.meta_empty': '尚無文字結果。',
        'module.general.text.output_empty': '尚無文字結果。',
        'module.general.text.meta': 'tokens={tokens} | model={model}',
        'module.general.image.prompt': '提示詞',
        'module.general.image.negative_prompt': '負向提示詞',
        'module.general.image.width': '寬度',
        'module.general.image.height': '高度',
        'module.general.image.steps': '步數',
        'module.general.image.guidance': 'Guidance',
        'module.general.image.seed_optional': 'Seed（選填）',
        'module.general.image.refiner_steps_optional': 'Refiner 步數（選填）',
        'module.general.image.skip_refiner': '略過 Refiner',
        'module.general.image.low_vram': '低 VRAM',
        'module.general.image.meta_empty': '尚未生成圖片。',
        'module.general.image.meta': '路徑={path} | seed={seed} | {width}x{height}',
        'module.general.translation.input_text': '輸入文字',
        'module.general.translation.source_language': '來源語言',
        'module.general.translation.target_language': '目標語言',
        'module.general.translation.beam_size': 'Beam 大小',
        'module.general.translation.dtype': 'DType',
        'module.general.translation.meta_empty': '尚無翻譯結果。',
        'module.general.translation.meta': '來源={source} -> 目標={target}',
        'module.general.voice.narration_text': '朗讀文字',
        'module.general.voice.language': '語言',
        'module.general.voice.speaker_wav_optional': 'Speaker WAV（選填）',
        'module.general.voice.speed': '語速',
        'module.general.voice.temperature': '溫度',
        'module.general.voice.meta_empty': '尚未生成音訊。',
        'module.general.voice.meta': '音訊={audio} | speaker={speaker}',
        'module.general.placeholder.text_prompt': '輸入問題或想執行的任務',
        'module.general.placeholder.image_prompt': '描述想生成的圖片',
        'module.general.placeholder.image_negative': '選填負向提示詞',
        'module.general.placeholder.translation_input': '貼上要翻譯的文字',
        'module.general.placeholder.voice_text': '輸入要合成語音的文字',
        'module.general.placeholder.voice_speaker_wav': 'runs/voice_samples/speaker-xxx.wav',
        'image.live_preview.title': '即時圖像預覽',
        'image.hint': '可先選一張圖查看原始提示詞與參數，再用編輯後設定重生成。',
        'image.selected': '目前選取影像',
        'image.positive': '正向提示詞',
        'image.negative': '負向提示詞',
        'btn.refresh_now': '立即刷新',
        'btn.save_template': '儲存模板',
        'btn.gallery_refresh': '刷新圖庫',
        'btn.start': '開始 / 加入佇列',
        'btn.stop': '停止目前任務',
        'btn.save_local': '儲存本機設定',
        'btn.load_local': '載入本機設定',
        'btn.save_version': '儲存設定版本',
        'btn.record_start': '開始錄音',
        'btn.record_stop': '停止錄音',
        'btn.record_save': '儲存為說話人 WAV',
        'btn.detail': '明細',
        'btn.stop_short': '停止',
        'btn.clear': '清除',
        'btn.clear_view': '清除主畫面',
        'btn.clear_module_view': '清除模組區',
        'btn.show_all': '顯示全部',
        'btn.clear_history': '清除營運紀錄',
        'btn.refresh_detail': '刷新明細',
        'btn.refresh_jobs': '刷新任務',
        'btn.refresh_evaluation': '刷新評估',
        'btn.stop_selected': '停止選取任務',
        'btn.refresh_images': '刷新圖片',
        'btn.refresh_story_list': '刷新故事清單',
        'btn.regen_selected': '重生成選取項目',
        'btn.queue_image_module': '加入圖像模組任務',
        'btn.regen_with_edits': '用目前編輯參數重生成',
        'btn.run_text_module': '執行文字模組',
        'btn.run_translation_module': '執行翻譯模組',
        'btn.run_voice_module': '執行語音模組',
        'btn.run_general_text': '執行通用文字',
        'btn.run_general_image': '執行通用圖像',
        'btn.run_general_translation': '執行通用翻譯',
        'btn.run_general_voice': '執行通用語音',
        'btn.apply': '套用',
        'btn.cancel': '取消',
        'btn.acknowledge': '確認',
        'btn.inspect': '檢視',
        'btn.select': '選取',
        'th.job': '任務',
        'th.state': '狀態',
        'th.priority': '優先序',
        'th.books': '書本數',
        'th.category': '類別',
        'th.age': '年齡層',
        'th.action': '操作',
        'th.version': '版本',
        'th.created': '建立時間',
        'th.note': '備註',
        'th.usage': '使用次數',
        'th.run': '執行編號',
        'th.started': '開始時間',
        'th.duration': '耗時',
        'th.result': '結果',
        'th.config': '設定',
        'th.type': '類型',
        'th.status': '狀態',
        'th.story_root': '故事路徑',
        'msg.request_failed': '請求失敗',
        'msg.refresh_failed': '刷新失敗。',
        'msg.select_module_job_first': '請先選擇一個模組任務。',
        'msg.no_module_jobs': '目前沒有模組任務。',
        'msg.no_module_job_selected': '尚未選擇模組任務。',
        'msg.no_events': '目前沒有事件。',
        'msg.no_module_logs': '目前沒有模組日誌。',
        'msg.submitting_module_job': '正在提交模組任務...',
        'msg.module_job_queued': '模組任務已加入佇列：{id}',
        'msg.failed_run_module_job': '執行模組任務失敗。',
        'msg.translation_targets_required': '請至少勾選一個目標語言。',
        'msg.loading_story_list': '正在載入可用故事清單...',
        'msg.story_list_load_failed': '載入故事清單失敗。',
        'msg.stop_requested_for_module_job': '已送出停止請求：{id}',
        'msg.failed_stop_module_job': '停止模組任務失敗。',
        'msg.none_selected': '尚未選取。',
        'msg.no_live_logs': '目前沒有正在執行的日誌。',
        'msg.no_generated_images': '目前尚無生成圖片。',
        'msg.select_at_least_one_image': '請至少選擇一個圖片項目。',
        'msg.regenerating_selected_images': '正在重生成已選圖片...',
        'msg.regenerated_images': '已重生成 {ok}/{total} 張圖片。',
        'msg.failed_regenerate_selected_images': '重生成選取圖片失敗。',
        'msg.select_image_for_regen': '請先選擇一張圖片再重生成。',
        'msg.regenerating_image_with_edits': '正在用編輯後參數重生成圖片...',
        'msg.image_regenerated_successfully': '圖片重生成成功。',
        'msg.image_regeneration_failed': '圖片重生成失敗。',
        'msg.failed_regenerate_image': '圖片重生成失敗。',
        'msg.recording_read_script': '錄音中...請自然朗讀腳本。',
        'msg.microphone_access_failed': '麥克風權限或裝置無法使用。',
        'msg.recording_captured': '錄音已完成，可預聽並儲存為說話人樣本。',
        'msg.no_recording_available': '目前沒有可儲存的錄音。',
        'msg.speaker_sample_saved': '說話人樣本已儲存：{path}',
        'msg.failed_save_recording': '儲存錄音失敗。',
        'msg.saved_local_profile': '已儲存本機設定。',
        'msg.preset_applied': '已套用預設：{name}',
        'msg.no_run_history': '目前沒有執行紀錄。',
        'confirm.clear_overview_view': '只清除主畫面即時資料嗎？營運中心紀錄會保留。',
        'msg.clearing_overview_view': '正在清除主畫面資料...',
        'msg.cleared_overview_view': '主畫面已清除（{count} 行即時日誌）。',
        'msg.failed_clear_overview_view': '清除主畫面資料失敗。',
        'confirm.clear_run_history': '要清除全部執行紀錄與相關日誌嗎？',
        'msg.clearing_run_history': '正在清除執行紀錄...',
        'msg.cleared_run_history': '已清除執行紀錄（{count} 筆）。',
        'msg.clear_history_blocked_running': '請先停止目前執行與排隊任務，再清除紀錄。',
        'msg.failed_clear_run_history': '清除執行紀錄失敗。',
        'msg.cleared_module_view': '已清除模組區顯示（隱藏 {count} 筆）。',
        'msg.module_view_restored': '已還原模組區，顯示全部紀錄。',
        'msg.module_view_already_clean': '模組區目前已是乾淨狀態。',
        'msg.no_runs_available': '目前沒有可選的執行紀錄',
        'msg.eval_loading': '正在載入評估報告...',
        'msg.eval_no_data': '尚未載入評估資料。',
        'msg.eval_no_dimensions': '此報告未包含維度分數。',
        'msg.eval_run_required': '請先選擇 Run ID。',
        'msg.eval_no_books': '此批次沒有可用書本明細。',
        'msg.eval_story_root_required': '請先輸入 story_root。',
        'msg.eval_fetch_failed': '載入評估報告失敗。',
        'msg.queue_empty': '佇列目前為空。',
        'msg.no_alerts': '目前沒有警示。',
        'msg.no_trend_data': '目前沒有趨勢資料。',
        'msg.no_saved_versions': '目前沒有儲存版本。',
        'msg.no_related_alerts': '目前沒有相關警示。',
        'msg.no_run_logs': '目前沒有執行日誌。',
        'msg.no_images_found': '目前找不到可顯示的圖片。',
        'msg.general_prompt_required': '請先輸入 Prompt。',
        'msg.general_text_required': '請先輸入文字內容。',
        'msg.general_voice_text_required': '請先輸入語音朗讀文字。',
        'msg.general_running': '請求執行中...',
        'msg.general_text_done': '通用文字生成完成。',
        'msg.general_image_done': '通用圖像生成完成。',
        'msg.general_translation_done': '通用翻譯完成。',
        'msg.general_voice_done': '通用語音生成完成。',
        'msg.general_request_failed': '通用請求失敗。',
        'msg.general_already_running': '已有請求執行中，請稍候。',
        'msg.prompt_empty': '請先輸入 Prompt 內容。',
        'msg.template_name_required': '請先輸入模板名稱。',
        'msg.book_count_min': '生成本數必須 >= 1。',
        'msg.submitting_run_request': '正在提交執行請求...',
        'msg.run_started': '已啟動任務：{id}',
        'msg.run_queued': '任務已加入佇列，位置 {pos}。',
        'msg.failed_start_run': '啟動任務失敗。',
        'msg.stopping_active_run': '正在停止目前任務...',
        'msg.stopped_and_started_next': '已停止目前任務，並啟動下一個排隊任務。',
        'msg.stopped': '已停止。',
        'msg.failed_stop_run': '停止任務失敗。',
        'msg.saved_config_version': '設定版本已儲存：{id}',
        'msg.failed_save_config_version': '儲存設定版本失敗。',
        'msg.applied_config_version': '已套用設定版本：{id}',
        'msg.failed_apply_config_version': '套用設定版本失敗。',
        'msg.updated_priority': '已更新任務優先序：{id}',
        'msg.failed_reprioritize_job': '更新優先序失敗。',
        'msg.canceled_job': '已取消排隊任務：{id}',
        'msg.failed_cancel_job': '取消任務失敗。',
        'msg.failed_ack_alert': '警示確認失敗。',
        'msg.loaded_local_profile': '已載入本機設定。',
        'msg.saving_template': '正在儲存模板...',
        'msg.template_saved': '模板已儲存。',
        'msg.template_save_failed': '模板儲存失敗。',
        'msg.template_loaded': '模板已載入。',
        'meta.book': '書本',
        'meta.stage': '階段',
        'meta.updated': '更新',
        'meta.count': '本數',
        'meta.retry': '重試',
        'meta.category': '類別',
        'meta.age': '年齡',
        'module.meta.job': '任務',
        'module.meta.type': '類型',
        'module.meta.status': '狀態',
        'module.meta.priority': '優先序',
        'module.meta.image_selected': '任務={task} | 類型={type} | 故事={story}',
        'state.idle': '閒置',
        'state.running': '執行中',
        'state.completed': '已完成',
        'state.failed': '失敗',
        'state.stopped': '已停止',
        'state.queued': '排隊中',
        'state.error': '錯誤',
        'state.active': '執行中',
        'placeholder.theme': '例如：友情、勇氣、冒險',
        'placeholder.subcategory': '例如：森林、傳統、科學',
        'placeholder.seed': '自動',
        'placeholder.story_prompt': '描述希望的風格、劇情方向、限制條件或情感走向。',
        'placeholder.story_materials': '每行一個素材，例如：\n魔法地圖\n古老大樹\n雨夜',
        'placeholder.story_prompt_preset': '預設模式：直接生成（不走轉換層）。',
        'placeholder.story_materials_preset': '預設模式：直接生成（不走轉換層）。',
        'placeholder.story_prompt_custom': '輸入精簡需求：情緒、價值、角色、衝突、結局風格。',
        'placeholder.story_materials_custom': '可貼上筆記、大綱、教材重點或家庭情境。',
        'placeholder.speaker_wav': '例如：models/XTTS-v2/samples/my_parent.wav',
        'placeholder.theme_custom': '例如：友情、勇氣、冒險',
        'placeholder.subcategory_custom': '例如：森林、傳統、科學',
        'placeholder.speaker_dir': '例如：models/XTTS-v2/samples/custom',
        'placeholder.version_name': '例如：quality-v3',
        'placeholder.version_note': '這版改了什麼、為什麼改',
        'placeholder.template_name': '模板名稱',
        'template.placeholder': '-- 載入模板 --',
        'prompt.template_name': '請輸入模板名稱：',
        'prompt.template_default_name': '兒童故事模板',
        'option.lang.zh_tw': '繁體中文',
        'option.lang.en': 'English',
        'option.story_input_mode.preset': '預設（使用 KG 預設）',
        'option.story_input_mode.custom': '自訂（轉換使用者輸入）',
        'option.module_story_input_mode.preset': '預設',
        'option.module_story_input_mode.custom': '自訂',
      },
    };

    const ui = {
      timer: null,
      logCursor: 0,
      activeLogRunId: null,
      historyRows: [],
      selectedRunId: '',
      selectedRunBookByRun: {},
      latestStatus: null,
      activeTab: 'overview',
      refreshTick: 0,
      recorder: null,
      recordChunks: [],
      recordSampleRate: 16000,
      recordBlob: null,
      recordStream: null,
      recordContext: null,
      recordSource: null,
      recordProcessor: null,
      imageItems: [],
      imageStoryRoot: '',
      imageSelectedTaskIds: {},
      imageDetailTaskId: '',
      moduleJobs: [],
      hiddenModuleJobs: {},
      moduleSelectedJobId: '',
      moduleStudio: 'story',
      translatableStories: [],
      moduleRecordChunks: [],
      moduleRecordSampleRate: 16000,
      moduleRecordBlob: null,
      moduleRecordStream: null,
      moduleRecordContext: null,
      moduleRecordSource: null,
      moduleRecordProcessor: null,
      language: 'zh-TW',
      generalBusy: {
        text: false,
        image: false,
        translation: false,
        voice: false,
      },
      evaluation: {
        source: 'latest',
        runId: '',
        book: '',
        storyRoot: '',
        branch: 'canonical',
        chart: null,
        lastResponse: null,
      },
      lastActionMessageTs: 0,
    };

    const SOURCE_LANG_CODE_BY_FOLDER = {
      en: 'eng_Latn',
      zh: 'zho_Hant',
      'zh-tw': 'zho_Hant',
      'zh-hant': 'zho_Hant',
      'zh-cn': 'zho_Hans',
      'zh-hans': 'zho_Hans',
      ja: 'jpn_Jpan',
      ko: 'kor_Hang',
      fr: 'fra_Latn',
      de: 'deu_Latn',
      es: 'spa_Latn',
      pt: 'por_Latn',
    };

    function getPreferredLanguage() {
      const saved = localStorage.getItem(LANG_STORE_KEY);
      if (saved && (saved === 'en' || saved === 'zh-TW')) return saved;
      const nav = String((navigator.language || navigator.userLanguage || '')).toLowerCase();
      if (nav.startsWith('zh')) return 'zh-TW';
      return 'en';
    }

    function t(key, fallback) {
      const lang = ui.language && I18N[ui.language] ? ui.language : 'en';
      const table = I18N[lang] || {};
      if (Object.prototype.hasOwnProperty.call(table, key)) return table[key];
      if (Object.prototype.hasOwnProperty.call(I18N.en, key)) return I18N.en[key];
      return fallback != null ? fallback : key;
    }

    function tf(key, vars, fallback) {
      let text = String(t(key, fallback));
      const payload = vars || {};
      const names = Object.keys(payload);
      for (let i = 0; i < names.length; i += 1) {
        const name = names[i];
        text = text.split('{' + name + '}').join(String(payload[name]));
      }
      return text;
    }

    function setTextById(id, key, fallback) {
      const node = byId(id);
      if (!node) return;
      node.textContent = t(key, fallback);
    }

    function applyLanguage() {
      document.documentElement.lang = ui.language;
      document.title = t('title.dashboard', 'GenAI Chief Control Plane');

      const staticMappings = [
        ['hero_eyebrow', 'hero.eyebrow', 'GenAI Operations'],
        ['hero_title', 'hero.title', 'Chief Control Plane'],
        ['hero_sub', 'hero.sub', 'Operate runs, inspect alerts, manage queue priority, and audit production history from one dashboard.'],
        ['label_auto_refresh_text', 'label.auto_refresh', 'Auto refresh'],
        ['label_language', 'label.language', 'Language'],
        ['kpi_label_system_state', 'kpi.system_state', 'System State'],
        ['kpi_label_queue_depth', 'kpi.queue_depth', 'Queue Depth'],
        ['kpi_label_success_rate', 'kpi.success_rate', 'Success Rate'],
        ['kpi_label_avg_duration', 'kpi.avg_duration', 'Avg Duration'],
        ['kpi_label_gpu_cost', 'kpi.gpu_cost', 'Est. GPU Cost'],
        ['label_tab_gallery', 'label.tab_gallery', 'Gallery'],
        ['label_tab_overview', 'tab.overview', 'Generate'],
        ['label_tab_ops', 'tab.ops', 'Operations'],
        ['label_tab_detail', 'tab.detail', 'Run Detail'],
        ['label_tab_evaluation', 'tab.evaluation', 'Evaluation'],
        ['label_tab_modules', 'tab.modules', 'Modules'],
        ['gallery_title', 'gallery.title', 'Story Gallery'],
        ['gallery_sub', 'gallery.sub', 'Browse generated stories with cover previews and quick metadata.'],
        ['gallery_status_title', 'gallery.system_title', 'System Snapshot'],
        ['gallery_status_hint', 'gallery.system_hint', 'Live resource usage helps avoid running heavy stages under memory pressure.'],
        ['overview_composer_title', 'overview.composer.title', 'Run Composer'],
        ['overview_composer_sub', 'overview.composer.sub', 'Product mode supports queueing with priority and versioned run profiles.'],
        ['overview_telemetry_title', 'overview.telemetry.title', 'Live Telemetry'],
        ['overview_live_logs_title', 'overview.logs.title', 'Live Logs (Now)'],
        ['overview_live_logs_hint', 'overview.logs.hint', 'Latest lines from the active run. Full logs are in Run Detail.'],
        ['ops_queue_title', 'ops.queue.title', 'Queue and Priority'],
        ['ops_alert_title', 'ops.alert.title', 'Alert Center'],
        ['ops_capacity_title', 'ops.capacity.title', 'Capacity and Cost'],
        ['cap_label_runs', 'ops.capacity.window_runs', 'Window Runs'],
        ['cap_label_success_rate', 'ops.capacity.success_rate', 'Success Rate'],
        ['cap_label_throughput', 'ops.capacity.books_per_hour', 'Books / Hour'],
        ['cap_label_queue_delay', 'ops.capacity.avg_queue_delay', 'Avg Queue Delay'],
        ['cap_label_gpu_hours', 'ops.capacity.gpu_hours', 'GPU Hours'],
        ['cap_label_gpu_cost', 'ops.capacity.gpu_cost', 'GPU Cost'],
        ['ops_config_title', 'ops.config.title', 'Config Versions'],
        ['ops_logs_title', 'ops.logs.title', 'Live Logs'],
        ['ops_recent_title', 'ops.recent.title', 'Recent Runs'],
        ['detail_selector_title', 'detail.selector.title', 'Run Detail Selector'],
        ['detail_summary_title', 'detail.summary.title', 'Run Summary'],
        ['detail_label_state', 'detail.summary.state', 'State'],
        ['detail_label_duration', 'detail.summary.duration', 'Duration'],
        ['detail_label_exit_code', 'detail.summary.exit_code', 'Exit Code'],
        ['detail_label_total_books', 'detail.summary.total_books', 'Total Books'],
        ['detail_label_success_books', 'detail.summary.success_books', 'Success Books'],
        ['detail_label_failed_books', 'detail.summary.failed_books', 'Failed Books'],
        ['detail_meta_priority', 'detail.summary.priority', 'Priority'],
        ['detail_label_book', 'detail.book', 'Book'],
        ['detail_meta_queue_delay', 'detail.summary.queue_delay', 'Queue Delay'],
        ['detail_meta_started_at', 'detail.summary.started_at', 'Started At'],
        ['detail_meta_finished_at', 'detail.summary.finished_at', 'Finished At'],
        ['detail_timeline_title', 'detail.timeline.title', 'Timeline and Alerts'],
        ['detail_related_alerts_title', 'detail.related_alerts.title', 'Related Alerts'],
        ['detail_logs_title', 'detail.logs.title', 'Run Logs'],
        ['evaluation_title', 'eval.title', 'Evaluation Diagnostics'],
        ['evaluation_sub', 'eval.sub', 'Inspect assessment reports by latest story, run ID, or manual story root.'],
        ['label_evaluation_source', 'eval.source', 'Data Source'],
        ['label_evaluation_run', 'eval.run_id', 'Run ID'],
        ['label_evaluation_book', 'eval.book', 'Book'],
        ['label_evaluation_story_root', 'eval.story_root', 'Story Root'],
        ['label_evaluation_branch', 'eval.branch', 'Branch'],
        ['eval_label_overall', 'eval.overall', 'Overall Score'],
        ['eval_label_scope', 'eval.scope', 'Scope'],
        ['eval_label_branch', 'eval.branch_used', 'Branch'],
        ['eval_label_report_file', 'eval.report_file', 'Report File'],
        ['eval_meta_source_label', 'eval.meta.source', 'Source'],
        ['eval_meta_run_label', 'eval.meta.run_id', 'Run ID'],
        ['eval_meta_book_label', 'eval.book', 'Book'],
        ['eval_meta_story_root_label', 'eval.meta.story_root', 'Story Root'],
        ['evaluation_chart_title', 'eval.chart.title', 'Dimension Radar'],
        ['evaluation_log_title', 'eval.log.title', 'Assessment JSON'],
        ['module_jobs_title', 'module.jobs.title', 'Module Jobs'],
        ['module_job_detail_title', 'module.job_detail.title', 'Module Job Detail'],
        ['module_job_events_title', 'module.job_events.title', 'Events'],
        ['module_job_logs_title', 'module.job_logs.title', 'Logs'],
        ['module_workbenches_title', 'module.workbenches.title', 'Module Workbenches'],
        ['module_workbenches_sub', 'module.workbenches.sub', 'Run text, image, translation, and voice independently without executing the full pipeline.'],
        ['module_tab_story', 'module.tab.story', 'Text Studio'],
        ['module_tab_image', 'module.tab.image', 'Image Studio'],
        ['module_tab_translation', 'module.tab.translation', 'Translation Studio'],
        ['module_tab_voice', 'module.tab.voice', 'Voice Studio'],
        ['module_tab_general', 'module.tab.general', 'General Studio'],
        ['general_tools_title', 'general.tools.title', 'General AI Toolkit'],
        ['general_tools_sub', 'general.tools.sub', 'Use direct non-story tools for text QA, image generation, translation, and TTS preview.'],
        ['general_section_text_title', 'module.general.section.text', 'General Text'],
        ['general_section_image_title', 'module.general.section.image', 'General Image'],
        ['general_section_translation_title', 'module.general.section.translation', 'General Translation'],
        ['general_section_voice_title', 'module.general.section.voice', 'General Voice (TTS)'],
        ['image_live_preview_title', 'image.live_preview.title', 'Live Image Preview'],
        ['image_hint_text', 'image.hint', 'Select one image to inspect original prompt and parameters, then regenerate with edits.'],
        ['image_selected_label', 'image.selected', 'Selected Image'],
        ['image_pos_label', 'image.positive', 'Positive Prompt'],
        ['image_neg_label', 'image.negative', 'Negative Prompt'],
        ['btn_refresh_now', 'btn.refresh_now', 'Refresh now'],
        ['btn_save_template', 'btn.save_template', 'Save Template'],
        ['btn_gallery_refresh', 'btn.gallery_refresh', 'Refresh Gallery'],
        ['btn_start', 'btn.start', 'Start / Queue'],
        ['btn_stop', 'btn.stop', 'Stop Active'],
        ['btn_save_local', 'btn.save_local', 'Save Local'],
        ['btn_load_local', 'btn.load_local', 'Load Local'],
        ['btn_save_version', 'btn.save_version', 'Save Config Version'],
        ['btn_record_start', 'btn.record_start', 'Start Recording'],
        ['btn_record_stop', 'btn.record_stop', 'Stop Recording'],
        ['btn_record_save', 'btn.record_save', 'Save As Speaker WAV'],
        ['btn_clear_logs', 'btn.clear', 'Clear'],
        ['btn_overview_clear_view', 'btn.clear_view', 'Clear View'],
        ['btn_clear_history', 'btn.clear_history', 'Clear Ops History'],
        ['btn_detail_refresh', 'btn.refresh_detail', 'Refresh Detail'],
        ['btn_eval_refresh', 'btn.refresh_evaluation', 'Refresh Evaluation'],
        ['btn_modules_refresh', 'btn.refresh_jobs', 'Refresh Jobs'],
        ['btn_module_clear_view', 'btn.clear_module_view', 'Clear View'],
        ['btn_module_show_all', 'btn.show_all', 'Show All'],
        ['btn_module_job_stop', 'btn.stop_selected', 'Stop Selected'],
        ['btn_images_refresh', 'btn.refresh_images', 'Refresh Images'],
        ['btn_module_trans_story_refresh', 'btn.refresh_story_list', 'Refresh Story List'],
        ['btn_images_regen', 'btn.regen_selected', 'Regenerate Selected'],
        ['btn_images_module_run', 'btn.queue_image_module', 'Queue Image Module Job'],
        ['btn_image_regen_detail', 'btn.regen_with_edits', 'Regenerate This (With Edits)'],
        ['btn_module_story_run', 'btn.run_text_module', 'Run Text Module'],
        ['btn_module_translation_run', 'btn.run_translation_module', 'Run Translation Module'],
        ['btn_module_voice_run', 'btn.run_voice_module', 'Run Voice Module'],
        ['btn_module_record_start', 'btn.record_start', 'Start Recording'],
        ['btn_module_record_stop', 'btn.record_stop', 'Stop Recording'],
        ['btn_module_record_save', 'btn.record_save', 'Save As Speaker WAV'],
        ['btn_general_text_run', 'btn.run_general_text', 'Run General Text'],
        ['btn_general_image_run', 'btn.run_general_image', 'Run General Image'],
        ['btn_general_translation_run', 'btn.run_general_translation', 'Run General Translation'],
        ['btn_general_voice_run', 'btn.run_general_voice', 'Run General Voice'],
        ['label_module_trans_story_select', 'module.translation.story_select', 'Story Book (auto detected)'],
        ['label_module_trans_target_list', 'module.translation.target_languages', 'Target Languages (multi-select)'],
        ['module_voice_record_hint', 'module.voice.record_hint', 'Record a speaker sample directly in Voice Studio and save it to Speaker WAV.'],
        ['th_queue_job', 'th.job', 'Job'],
        ['th_queue_state', 'th.state', 'State'],
        ['th_queue_priority', 'th.priority', 'Priority'],
        ['th_queue_books', 'th.books', 'Books'],
        ['th_queue_category', 'th.category', 'Category'],
        ['th_queue_age', 'th.age', 'Age'],
        ['th_queue_action', 'th.action', 'Action'],
        ['th_cfg_version', 'th.version', 'Version'],
        ['th_cfg_created', 'th.created', 'Created'],
        ['th_cfg_note', 'th.note', 'Note'],
        ['th_cfg_usage', 'th.usage', 'Usage'],
        ['th_cfg_action', 'th.action', 'Action'],
        ['th_recent_run', 'th.run', 'Run'],
        ['th_recent_started', 'th.started', 'Started'],
        ['th_recent_duration', 'th.duration', 'Duration'],
        ['th_recent_result', 'th.result', 'Result'],
        ['th_recent_books', 'th.books', 'Books'],
        ['th_recent_config', 'th.config', 'Config'],
        ['th_module_job', 'th.job', 'Job'],
        ['th_module_type', 'th.type', 'Type'],
        ['th_module_status', 'th.status', 'Status'],
        ['th_module_priority', 'th.priority', 'Priority'],
        ['th_module_story_root', 'th.story_root', 'Story Root'],
        ['th_module_action', 'th.action', 'Action'],
      ];

      for (let i = 0; i < staticMappings.length; i += 1) {
        const row = staticMappings[i];
        setTextById(row[0], row[1], row[2]);
      }

      const selectorMappings = [
        ['#tab_overview label[for="count"]', 'overview.field.book_count', 'Book Count'],
        ['#tab_overview label[for="max_retries"]', 'overview.field.retry_per_book', 'Retry Per Book'],
        ['#tab_overview label[for="priority"]', 'overview.field.queue_priority', 'Queue Priority'],
        ['#tab_overview label[for="age"]', 'overview.field.age', 'Age'],
        ['#tab_overview label[for="category"]', 'overview.field.category', 'Category'],
        ['#tab_overview label[for="theme"]', 'overview.field.theme_preset', 'Theme (preset)'],
        ['#tab_overview label[for="subcategory"]', 'overview.field.subcategory_preset', 'Subcategory (preset)'],
        ['#tab_overview label[for="story_input_mode"]', 'overview.field.story_input_mode', 'Story Input Mode'],
        ['#tab_overview label[for="speaker_wav"]', 'overview.field.speaker_wav_optional', 'Speaker WAV (optional)'],
        ['#tab_overview label[for="theme_custom"]', 'overview.field.theme_custom', 'Theme (custom)'],
        ['#tab_overview label[for="subcategory_custom"]', 'overview.field.subcategory_custom', 'Subcategory (custom)'],
        ['#tab_overview label[for="pages"]', 'overview.field.pages_auto', 'Pages (0 = auto)'],
        ['#tab_overview label[for="seed"]', 'overview.field.seed_auto', 'Seed (empty = auto)'],
        ['#tab_overview label[for="story_prompt"]', 'overview.field.story_prompt_free', 'Story Prompt (free text)'],
        ['#tab_overview label[for="story_materials"]', 'overview.field.materials_elements', 'Materials / Elements'],
        ['#tab_overview label[for="speaker_dir"]', 'overview.field.speaker_dir_optional', 'Speaker Samples Dir (optional)'],
        ['#tab_overview label[for="voice_script"]', 'overview.field.recording_script_recommended', 'Recording Script (recommended)'],
        ['#tab_overview label[for="version_name"]', 'overview.field.config_version_name', 'Config Version Name'],
        ['#tab_overview label[for="version_note"]', 'overview.field.version_note', 'Version Note'],
        ['#studio_story label[for="module_story_count"]', 'module.story.book_count', 'Book Count'],
        ['#studio_story label[for="module_story_pages"]', 'module.story.pages_auto', 'Pages (0 = auto)'],
        ['#studio_story label[for="module_story_priority"]', 'module.story.priority', 'Priority'],
        ['#studio_story label[for="module_story_age"]', 'module.story.age', 'Age'],
        ['#studio_story label[for="module_story_category"]', 'module.story.category', 'Category'],
        ['#studio_story label[for="module_story_input_mode"]', 'module.story.input_mode', 'Input Mode'],
        ['#studio_story label[for="module_story_theme_select"]', 'module.story.theme_preset', 'Theme (preset)'],
        ['#studio_story label[for="module_story_subcategory_select"]', 'module.story.subcategory_preset', 'Subcategory (preset)'],
        ['#studio_story label[for="module_story_theme"]', 'module.story.theme_custom', 'Theme (custom)'],
        ['#studio_story label[for="module_story_subcategory"]', 'module.story.subcategory_custom', 'Subcategory (custom)'],
        ['#studio_story label[for="module_story_seed"]', 'module.story.seed_optional', 'Seed (optional)'],
        ['#studio_story label[for="module_story_prompt"]', 'module.story.prompt_custom', 'Story Prompt (custom mode)'],
        ['#studio_story label[for="module_story_materials"]', 'module.story.materials_custom', 'Story Materials (custom mode)'],
        ['#studio_image label[for="module_image_priority"]', 'module.image.job_priority', 'Module Job Priority'],
        ['#studio_image label[for="image_width"]', 'module.image.width', 'Width'],
        ['#studio_image label[for="image_height"]', 'module.image.height', 'Height'],
        ['#studio_image label[for="image_steps"]', 'module.image.steps', 'Steps'],
        ['#studio_image label[for="image_guidance"]', 'module.image.guidance', 'Guidance'],
        ['#studio_image label[for="image_seed"]', 'module.image.seed', 'Seed'],
        ['#studio_image label[for="image_refiner_steps"]', 'module.image.refiner_steps', 'Refiner Steps'],
        ['#studio_translation label[for="module_trans_story_select"]', 'module.translation.story_select', 'Story Book (auto detected)'],
        ['#studio_translation label[for="module_trans_story_root"]', 'module.translation.story_root_optional', 'Story Root (optional)'],
        ['#studio_translation label[for="module_trans_priority"]', 'module.translation.priority', 'Priority'],
        ['#studio_translation label[for="module_trans_source_folder"]', 'module.translation.source_folder', 'Source Folder'],
        ['#studio_translation label[for="module_trans_source_lang"]', 'module.translation.source_lang_code', 'Source Language Code'],
        ['#studio_translation label[for="module_trans_beam"]', 'module.translation.beam_size', 'Beam Size'],
        ['#studio_translation label[for="module_trans_length_penalty"]', 'module.translation.length_penalty', 'Length Penalty'],
        ['#studio_translation label[for="module_trans_device"]', 'module.translation.device', 'Device'],
        ['#studio_translation label[for="module_trans_dtype"]', 'module.translation.dtype', 'DType'],
        ['#label_module_trans_target_list', 'module.translation.target_languages', 'Target Languages (multi-select)'],
        ['#studio_voice label[for="module_voice_story_root"]', 'module.voice.story_root_optional', 'Story Root (optional)'],
        ['#studio_voice label[for="module_voice_language"]', 'module.voice.language_auto', 'Language (blank = auto detect)'],
        ['#studio_voice label[for="module_voice_speaker_wav"]', 'module.voice.speaker_wav_optional', 'Speaker WAV (optional)'],
        ['#studio_voice label[for="module_voice_speaker_dir"]', 'module.voice.speaker_dir_optional', 'Speaker Dir (optional)'],
        ['#studio_voice label[for="module_voice_record_script"]', 'module.voice.record_script_optional', 'Recording Script (optional)'],
        ['#studio_voice label[for="module_voice_page_start"]', 'module.voice.page_start_optional', 'Page Start (optional)'],
        ['#studio_voice label[for="module_voice_page_end"]', 'module.voice.page_end_optional', 'Page End (optional)'],
        ['#studio_voice label[for="module_voice_priority"]', 'module.voice.priority', 'Priority'],
        ['#studio_voice label[for="module_voice_gain"]', 'module.voice.gain', 'Gain'],
        ['#studio_voice label[for="module_voice_speed"]', 'module.voice.speed', 'Speed'],
        ['#studio_voice label[for="module_voice_device"]', 'module.voice.device', 'Device'],
        ['#studio_general label[for="general_text_prompt"]', 'module.general.text.prompt', 'Prompt'],
        ['#studio_general label[for="general_text_system"]', 'module.general.text.system_instruction', 'System Instruction'],
        ['#studio_general label[for="general_text_max_tokens"]', 'module.general.text.max_tokens', 'Max Tokens'],
        ['#studio_general label[for="general_text_temperature"]', 'module.general.text.temperature', 'Temperature'],
        ['#studio_general label[for="general_text_top_p"]', 'module.general.text.top_p', 'Top P'],
        ['#studio_general label[for="general_text_top_k"]', 'module.general.text.top_k', 'Top K'],
        ['#studio_general label[for="general_image_prompt"]', 'module.general.image.prompt', 'Prompt'],
        ['#studio_general label[for="general_image_negative"]', 'module.general.image.negative_prompt', 'Negative Prompt'],
        ['#studio_general label[for="general_image_width"]', 'module.general.image.width', 'Width'],
        ['#studio_general label[for="general_image_height"]', 'module.general.image.height', 'Height'],
        ['#studio_general label[for="general_image_steps"]', 'module.general.image.steps', 'Steps'],
        ['#studio_general label[for="general_image_guidance"]', 'module.general.image.guidance', 'Guidance'],
        ['#studio_general label[for="general_image_seed"]', 'module.general.image.seed_optional', 'Seed (optional)'],
        ['#studio_general label[for="general_image_refiner_steps"]', 'module.general.image.refiner_steps_optional', 'Refiner Steps (optional)'],
        ['#studio_general label[for="general_trans_text"]', 'module.general.translation.input_text', 'Input Text'],
        ['#studio_general label[for="general_trans_source"]', 'module.general.translation.source_language', 'Source Language'],
        ['#studio_general label[for="general_trans_target"]', 'module.general.translation.target_language', 'Target Language'],
        ['#studio_general label[for="general_trans_beam"]', 'module.general.translation.beam_size', 'Beam Size'],
        ['#studio_general label[for="general_trans_dtype"]', 'module.general.translation.dtype', 'DType'],
        ['#studio_general label[for="general_voice_text"]', 'module.general.voice.narration_text', 'Narration Text'],
        ['#studio_general label[for="general_voice_language"]', 'module.general.voice.language', 'Language'],
        ['#studio_general label[for="general_voice_speaker_wav"]', 'module.general.voice.speaker_wav_optional', 'Speaker WAV (optional)'],
        ['#studio_general label[for="general_voice_speed"]', 'module.general.voice.speed', 'Speed'],
        ['#studio_general label[for="general_voice_temperature"]', 'module.general.voice.temperature', 'Temperature'],
      ];

      for (let i = 0; i < selectorMappings.length; i += 1) {
        const row = selectorMappings[i];
        const nodes = document.querySelectorAll(row[0]);
        for (let j = 0; j < nodes.length; j += 1) {
          nodes[j].textContent = t(row[1], row[2]);
        }
      }

      const moduleStoryLowVram = document.querySelector('#studio_story label.chip-check input#module_story_low_vram');
      if (moduleStoryLowVram && moduleStoryLowVram.parentElement) {
        moduleStoryLowVram.parentElement.lastChild.textContent = t('module.story.low_vram', 'Low VRAM');
      }

      const overviewPhoto = document.querySelector('#tab_overview label.chip-check input#photo_enabled');
      if (overviewPhoto && overviewPhoto.parentElement) {
        overviewPhoto.parentElement.lastChild.textContent = t('overview.toggle.photo', 'Photo');
      }
      const overviewTranslation = document.querySelector('#tab_overview label.chip-check input#translation_enabled');
      if (overviewTranslation && overviewTranslation.parentElement) {
        overviewTranslation.parentElement.lastChild.textContent = t('overview.toggle.translation', 'Translation');
      }
      const overviewVoice = document.querySelector('#tab_overview label.chip-check input#voice_enabled');
      if (overviewVoice && overviewVoice.parentElement) {
        overviewVoice.parentElement.lastChild.textContent = t('overview.toggle.voice', 'Voice');
      }
      const overviewVerify = document.querySelector('#tab_overview label.chip-check input#verify_enabled');
      if (overviewVerify && overviewVerify.parentElement) {
        overviewVerify.parentElement.lastChild.textContent = t('overview.toggle.verify', 'Verify');
      }
      const overviewLowVram = document.querySelector('#tab_overview label.chip-check input#low_vram');
      if (overviewLowVram && overviewLowVram.parentElement) {
        overviewLowVram.parentElement.lastChild.textContent = t('overview.toggle.low_vram', 'Low VRAM');
      }
      const overviewStrictTranslation = document.querySelector('#tab_overview label.chip-check input#strict_translation');
      if (overviewStrictTranslation && overviewStrictTranslation.parentElement) {
        overviewStrictTranslation.parentElement.lastChild.textContent = t('overview.toggle.strict_translation', 'Strict translation');
      }
      const overviewStrictVoice = document.querySelector('#tab_overview label.chip-check input#strict_voice');
      if (overviewStrictVoice && overviewStrictVoice.parentElement) {
        overviewStrictVoice.parentElement.lastChild.textContent = t('overview.toggle.strict_voice', 'Strict voice');
      }

      const presetButtons = document.querySelectorAll('#tab_overview button[data-preset]');
      for (let i = 0; i < presetButtons.length; i += 1) {
        const btn = presetButtons[i];
        const preset = String(btn.getAttribute('data-preset') || '').toLowerCase();
        if (!preset) continue;
        btn.textContent = t('overview.preset.' + preset, btn.textContent);
      }

      setTextById('overview_metric_total', 'overview.metric.total', 'Total');
      setTextById('overview_metric_completed', 'overview.metric.completed', 'Completed');
      setTextById('overview_metric_success', 'overview.metric.success', 'Success');
      setTextById('overview_metric_failed', 'overview.metric.failed', 'Failed');
      setTextById('overview_metric_elapsed', 'overview.metric.elapsed', 'Elapsed');
      setTextById('overview_metric_eta', 'overview.metric.eta', 'ETA');
      setTextById('overview_meta_run_id', 'overview.meta.run_id', 'Run ID');
      setTextById('overview_meta_pid', 'overview.meta.pid', 'PID');
      setTextById('overview_meta_exit_code', 'overview.meta.exit_code', 'Exit Code');
      setTextById('overview_meta_queue_depth', 'overview.meta.queue_depth', 'Queue Depth');
      const overviewLogOutput = byId('overview_log_output');
      if (overviewLogOutput) {
        const oldText = String(overviewLogOutput.textContent || '').trim();
        if (!oldText || oldText === 'No active run logs yet.' || oldText === '目前沒有正在執行的日誌。') {
          overviewLogOutput.textContent = t('msg.no_live_logs', 'No active run logs yet.');
        }
      }
      const imageSkipRefiner = document.querySelector('#studio_image label.chip-check input#image_skip_refiner');
      if (imageSkipRefiner && imageSkipRefiner.parentElement) {
        imageSkipRefiner.parentElement.lastChild.textContent = ' ' + t('module.image.skip_refiner', 'Skip refiner');
      }
      const voiceConcat = document.querySelector('#studio_voice label.chip-check input#module_voice_concat');
      if (voiceConcat && voiceConcat.parentElement) {
        voiceConcat.parentElement.lastChild.textContent = t('module.voice.concat_full_narration', 'Concat full narration');
      }
      const voiceKeepRaw = document.querySelector('#studio_voice label.chip-check input#module_voice_keep_raw');
      if (voiceKeepRaw && voiceKeepRaw.parentElement) {
        voiceKeepRaw.parentElement.lastChild.textContent = t('module.voice.keep_raw_files', 'Keep raw files');
      }
      const generalSkipRefiner = document.querySelector('#studio_general label.chip-check input#general_image_skip_refiner');
      if (generalSkipRefiner && generalSkipRefiner.parentElement) {
        generalSkipRefiner.parentElement.lastChild.textContent = t('module.general.image.skip_refiner', 'Skip Refiner');
      }
      const generalLowVram = document.querySelector('#studio_general label.chip-check input#general_image_low_vram');
      if (generalLowVram && generalLowVram.parentElement) {
        generalLowVram.parentElement.lastChild.textContent = t('module.general.image.low_vram', 'Low VRAM');
      }

      const transStorySelect = byId('module_trans_story_select');
      if (transStorySelect && transStorySelect.options && transStorySelect.options.length > 0) {
        if (!String(transStorySelect.options[0].value || '')) {
          transStorySelect.options[0].text = t('module.translation.story_select_placeholder', '-- Select a story book --');
        }
      }

      const sourceLangSelect = byId('module_trans_source_lang');
      if (sourceLangSelect && sourceLangSelect.options) {
        for (let i = 0; i < sourceLangSelect.options.length; i += 1) {
          const option = sourceLangSelect.options[i];
          const key = 'module.translation.code.' + String(option.value || '').toLowerCase();
          option.text = t(key, option.text);
        }
      }

      const targetLangChecks = document.querySelectorAll('#module_trans_target_list input[type="checkbox"][data-lang]');
      for (let i = 0; i < targetLangChecks.length; i += 1) {
        const input = targetLangChecks[i];
        const label = input.parentElement;
        if (!label) continue;
        const code = String(input.getAttribute('data-lang') || '').toLowerCase();
        const text = t('module.translation.lang.' + code, label.textContent || code);
        label.lastChild.textContent = text;
      }

      const placeholderMappings = [
        ['speaker_wav', 'placeholder.speaker_wav', 'ex: models/XTTS-v2/samples/my_parent.wav'],
        ['theme_custom', 'placeholder.theme_custom', 'ex: friendship, courage, mystery'],
        ['subcategory_custom', 'placeholder.subcategory_custom', 'ex: forest, tradition, science'],
        ['speaker_dir', 'placeholder.speaker_dir', 'ex: models/XTTS-v2/samples/custom'],
        ['template_name_input', 'placeholder.template_name', 'Template name'],
        ['version_name', 'placeholder.version_name', 'example: quality-v3'],
        ['version_note', 'placeholder.version_note', 'what changed and why'],
        ['module_story_theme', 'module.placeholder.optional', 'optional'],
        ['module_story_subcategory', 'module.placeholder.optional', 'optional'],
        ['module_trans_story_root', 'module.placeholder.story_root', 'output/.../story_name'],
        ['module_voice_story_root', 'module.placeholder.story_root', 'output/.../story_name'],
        ['module_voice_language', 'module.placeholder.language', 'en'],
        ['module_voice_speaker_wav', 'module.placeholder.speaker_wav', 'runs/voice_samples/speaker-xxx.wav'],
        ['module_voice_speaker_dir', 'module.placeholder.speaker_dir', 'models/XTTS-v2/samples'],
        ['module_voice_record_script', 'module.voice.record_script_optional', 'Recording Script (optional)'],
        ['general_text_prompt', 'module.general.placeholder.text_prompt', 'Ask a question or describe a task'],
        ['general_image_prompt', 'module.general.placeholder.image_prompt', 'Describe the image you want'],
        ['general_image_negative', 'module.general.placeholder.image_negative', 'Optional negative prompt'],
        ['general_trans_text', 'module.general.placeholder.translation_input', 'Paste text to translate'],
        ['general_voice_text', 'module.general.placeholder.voice_text', 'Type text to synthesize'],
        ['general_voice_speaker_wav', 'module.general.placeholder.voice_speaker_wav', 'runs/voice_samples/speaker-xxx.wav'],
      ];

      for (let i = 0; i < placeholderMappings.length; i += 1) {
        const row = placeholderMappings[i];
        const node = byId(row[0]);
        if (node) node.placeholder = t(row[1], row[2]);
      }

      const prioritySelectIds = ['priority', 'module_story_priority', 'module_image_priority', 'module_trans_priority', 'module_voice_priority'];
      for (let i = 0; i < prioritySelectIds.length; i += 1) {
        const select = byId(prioritySelectIds[i]);
        if (!select || !select.options) continue;
        for (let j = 0; j < select.options.length; j += 1) {
          const option = select.options[j];
          const value = String(option.value || '').toLowerCase();
          if (value === 'high' || value === 'normal' || value === 'low') {
            option.text = t('module.priority.' + value, option.text);
          }
        }
      }

      const autoSelectIds = ['age', 'category', 'theme', 'subcategory', 'module_story_age', 'module_story_category', 'module_story_theme_select', 'module_story_subcategory_select'];
      for (let i = 0; i < autoSelectIds.length; i += 1) {
        const select = byId(autoSelectIds[i]);
        if (!select || !select.options) continue;
        for (let j = 0; j < select.options.length; j += 1) {
          const option = select.options[j];
          if (String(option.value || '') === '') {
            option.text = t('module.option.auto', option.text);
          }
        }
      }

      const categorySelectIds = ['category', 'module_story_category'];
      for (let k = 0; k < categorySelectIds.length; k += 1) {
        const categorySelect = byId(categorySelectIds[k]);
        if (!categorySelect || !categorySelect.options) continue;
        for (let i = 0; i < categorySelect.options.length; i += 1) {
          const option = categorySelect.options[i];
          const value = String(option.value || '').toLowerCase();
          if (!value) continue;
          option.text = t('module.category.' + value, option.text);
        }
      }

      const themeSelectIds = ['theme', 'module_story_theme_select'];
      for (let k = 0; k < themeSelectIds.length; k += 1) {
        const themeSelect = byId(themeSelectIds[k]);
        if (!themeSelect || !themeSelect.options) continue;
        for (let i = 0; i < themeSelect.options.length; i += 1) {
          const option = themeSelect.options[i];
          const value = String(option.value || '').toLowerCase();
          if (!value) continue;
          option.text = t('module.theme.' + value, option.text);
        }
      }

      const subcategorySelectIds = ['subcategory', 'module_story_subcategory_select'];
      for (let k = 0; k < subcategorySelectIds.length; k += 1) {
        const subcategorySelect = byId(subcategorySelectIds[k]);
        if (!subcategorySelect || !subcategorySelect.options) continue;
        for (let i = 0; i < subcategorySelect.options.length; i += 1) {
          const option = subcategorySelect.options[i];
          const value = String(option.value || '').toLowerCase();
          if (!value) continue;
          option.text = t('module.subcategory.' + value, option.text);
        }
      }

      const emptyTextStates = ['No text result yet.', '尚無文字結果。'];
      const emptyImageStates = ['No image generated yet.', '尚未生成圖片。'];
      const emptyTranslationStates = ['No translation yet.', '尚無翻譯結果。'];
      const emptyVoiceStates = ['No audio generated yet.', '尚未生成音訊。'];

      const generalTextMeta = byId('general_text_meta');
      if (generalTextMeta && emptyTextStates.includes(String(generalTextMeta.textContent || '').trim())) {
        generalTextMeta.textContent = t('module.general.text.meta_empty', 'No text result yet.');
      }
      const generalTextOutput = byId('general_text_output');
      if (generalTextOutput && emptyTextStates.includes(String(generalTextOutput.textContent || '').trim())) {
        generalTextOutput.textContent = t('module.general.text.output_empty', 'No text result yet.');
      }
      const generalImageMeta = byId('general_image_meta');
      if (generalImageMeta && emptyImageStates.includes(String(generalImageMeta.textContent || '').trim())) {
        generalImageMeta.textContent = t('module.general.image.meta_empty', 'No image generated yet.');
      }
      const generalTransMeta = byId('general_trans_meta');
      if (generalTransMeta && emptyTranslationStates.includes(String(generalTransMeta.textContent || '').trim())) {
        generalTransMeta.textContent = t('module.general.translation.meta_empty', 'No translation yet.');
      }
      const generalVoiceMeta = byId('general_voice_meta');
      if (generalVoiceMeta && emptyVoiceStates.includes(String(generalVoiceMeta.textContent || '').trim())) {
        generalVoiceMeta.textContent = t('module.general.voice.meta_empty', 'No audio generated yet.');
      }

      const moduleJobsBody = byId('module_jobs_body');
      if (moduleJobsBody && (!ui.moduleJobs || ui.moduleJobs.length === 0)) {
        moduleJobsBody.innerHTML = '<tr><td colspan="6">' + t('msg.no_module_jobs', 'No module jobs.') + '</td></tr>';
      }

      const moduleJobMeta = byId('module_job_meta');
      if (moduleJobMeta) {
        const old = String(moduleJobMeta.textContent || '').trim();
        if (old === 'No module job selected.' || old === '尚未選擇模組任務。') {
          moduleJobMeta.textContent = t('msg.no_module_job_selected', 'No module job selected.');
        }
      }

      const moduleJobLogs = byId('module_job_logs');
      if (moduleJobLogs) {
        const old = String(moduleJobLogs.textContent || '').trim();
        if (old === 'No module logs.' || old === '目前沒有模組日誌。') {
          moduleJobLogs.textContent = t('msg.no_module_logs', 'No module logs.');
        }
      }

      const moduleJobEvents = byId('module_job_events');
      if (moduleJobEvents && moduleJobEvents.children && moduleJobEvents.children.length === 1) {
        const first = moduleJobEvents.children[0];
        const old = String(first.textContent || '').trim();
        if (old === 'No events.' || old === '目前沒有事件。') {
          first.textContent = t('msg.no_events', 'No events.');
        }
      }

      const imageGallery = byId('image_gallery');
      if (imageGallery && (!ui.imageItems || ui.imageItems.length === 0) && imageGallery.children && imageGallery.children.length === 1) {
        const first = imageGallery.children[0];
        const old = String(first.textContent || '').trim();
        if (old === 'No generated images yet.' || old === '目前尚無生成圖片。') {
          first.textContent = t('msg.no_generated_images', 'No generated images yet.');
        }
      }

      const imageDetailMeta = byId('image_detail_meta');
      if (imageDetailMeta) {
        const old = String(imageDetailMeta.textContent || '').trim();
        if (old === 'None selected.' || old === '尚未選取。') {
          imageDetailMeta.textContent = t('msg.none_selected', 'None selected.');
        }
      }

      const themeInput = byId('theme');
      if (themeInput) themeInput.placeholder = t('placeholder.theme', themeInput.placeholder);
      const subcategoryInput = byId('subcategory');
      if (subcategoryInput) subcategoryInput.placeholder = t('placeholder.subcategory', subcategoryInput.placeholder);
      const seedInput = byId('seed');
      if (seedInput) seedInput.placeholder = t('placeholder.seed', seedInput.placeholder);
      const storyPrompt = byId('story_prompt');
      if (storyPrompt) storyPrompt.placeholder = t('placeholder.story_prompt', storyPrompt.placeholder);
      const storyMaterials = byId('story_materials');
      if (storyMaterials) storyMaterials.placeholder = t('placeholder.story_materials', storyMaterials.placeholder);

      const storyInputMode = byId('story_input_mode');
      if (storyInputMode && storyInputMode.options && storyInputMode.options.length >= 2) {
        storyInputMode.options[0].text = t('option.story_input_mode.preset', storyInputMode.options[0].text);
        storyInputMode.options[1].text = t('option.story_input_mode.custom', storyInputMode.options[1].text);
      }

      const moduleStoryInputMode = byId('module_story_input_mode');
      if (moduleStoryInputMode && moduleStoryInputMode.options && moduleStoryInputMode.options.length >= 2) {
        moduleStoryInputMode.options[0].text = t('option.module_story_input_mode.preset', moduleStoryInputMode.options[0].text);
        moduleStoryInputMode.options[1].text = t('option.module_story_input_mode.custom', moduleStoryInputMode.options[1].text);
      }

      const langSelect = byId('lang_select');
      if (langSelect) {
        if (langSelect.options && langSelect.options.length >= 2) {
          langSelect.options[0].text = t('option.lang.zh_tw', langSelect.options[0].text);
          langSelect.options[1].text = t('option.lang.en', langSelect.options[1].text);
        }
        langSelect.value = ui.language;
      }

      const evalSource = byId('evaluation_source');
      if (evalSource && evalSource.options && evalSource.options.length >= 3) {
        evalSource.options[0].text = t('eval.source.latest', evalSource.options[0].text);
        evalSource.options[1].text = t('eval.source.run', evalSource.options[1].text);
        evalSource.options[2].text = t('eval.source.story_root', evalSource.options[2].text);
      }

      const evalBookSelect = byId('eval_book_select');
      if (evalBookSelect && evalBookSelect.options && evalBookSelect.options.length === 1) {
        evalBookSelect.options[0].text = t('eval.book.latest', evalBookSelect.options[0].text || 'Latest book');
      }

      const detailBookSelect = byId('detail_book_select');
      if (detailBookSelect && detailBookSelect.options && detailBookSelect.options.length === 1) {
        detailBookSelect.options[0].text = t('eval.book.latest', detailBookSelect.options[0].text || 'Latest book');
      }

      const evalLogs = byId('eval_logs');
      if (evalLogs) {
        const old = String(evalLogs.textContent || '').trim();
        if (
          old === 'No evaluation loaded.' ||
          old === '尚未載入評估資料。' ||
          old === 'Loading...' ||
          old === '載入中...'
        ) {
          evalLogs.textContent = t('msg.eval_no_data', 'No evaluation loaded.');
        }
      }

      const templateSelect = byId('template_select');
      if (templateSelect && templateSelect.options && templateSelect.options.length > 0) {
        templateSelect.options[0].text = t('template.placeholder', templateSelect.options[0].text);
      }

      const transStorySelectNode = byId('module_trans_story_select');
      let selectedStory = null;
      if (transStorySelectNode) {
        const selectedRoot = String(transStorySelectNode.value || '').trim();
        for (let i = 0; i < ui.translatableStories.length; i += 1) {
          const row = ui.translatableStories[i] || {};
          if (String(row.story_root || '') === selectedRoot) {
            selectedStory = row;
            break;
          }
        }
      }
      updateTranslationStoryMeta(selectedStory);

      if (ui.evaluation && ui.evaluation.lastResponse) {
        renderEvaluation(ui.evaluation.lastResponse, {preserveStatus: true});
      }
    }

    function byId(id) {
      return document.getElementById(id);
    }

    function escapeHtml(value) {
      return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    function parseIntSafe(value, fallback) {
      const n = parseInt(String(value), 10);
      return Number.isFinite(n) ? n : fallback;
    }

    function parseFloatSafe(value, fallback) {
      const n = parseFloat(String(value));
      return Number.isFinite(n) ? n : fallback;
    }

    function formatDuration(seconds) {
      if (seconds == null || !Number.isFinite(Number(seconds))) return '-';
      const total = Math.max(0, Math.round(Number(seconds)));
      const h = Math.floor(total / 3600);
      const m = Math.floor((total % 3600) / 60);
      const s = total % 60;
      if (h > 0) {
        return String(h) + 'h ' + String(m).padStart(2, '0') + 'm ' + String(s).padStart(2, '0') + 's';
      }
      if (m > 0) {
        return String(m) + 'm ' + String(s).padStart(2, '0') + 's';
      }
      return String(s) + 's';
    }

    function toPercent(value) {
      const n = Number(value);
      if (!Number.isFinite(n)) return '0%';
      return n.toFixed(1) + '%';
    }

    function isoToLocal(isoText) {
      if (!isoText) return '-';
      const d = new Date(isoText);
      if (Number.isNaN(d.getTime())) return '-';
      return d.toLocaleString();
    }

    function localizeState(stateValue) {
      const value = String(stateValue || '').toLowerCase();
      if (!value) return '-';
      return t('state.' + value, value);
    }

    async function apiGet(path) {
      const res = await fetch(path);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || t('msg.request_failed', 'Request failed'));
      }
      return data;
    }

    async function apiPost(path, payload) {
      const res = await fetch(path, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload || {}),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) {
        throw new Error(data.error || t('msg.request_failed', 'Request failed'));
      }
      return data;
    }

    function loadHiddenModuleJobs() {
      try {
        const raw = localStorage.getItem(MODULE_HIDDEN_JOBS_KEY);
        if (!raw) {
          ui.hiddenModuleJobs = {};
          return;
        }
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') {
          ui.hiddenModuleJobs = {};
          return;
        }
        const next = {};
        const keys = Object.keys(parsed);
        for (let i = 0; i < keys.length; i += 1) {
          const k = String(keys[i] || '').trim();
          if (!k) continue;
          if (parsed[k]) next[k] = 1;
        }
        ui.hiddenModuleJobs = next;
      } catch (_err) {
        ui.hiddenModuleJobs = {};
      }
    }

    function saveHiddenModuleJobs() {
      try {
        localStorage.setItem(MODULE_HIDDEN_JOBS_KEY, JSON.stringify(ui.hiddenModuleJobs || {}));
      } catch (_err) {
      }
    }

    function isModuleJobHidden(jobId) {
      const id = String(jobId || '').trim();
      if (!id) return false;
      return !!(ui.hiddenModuleJobs && ui.hiddenModuleJobs[id]);
    }

    function setMessage(text, mode) {
      const el = byId('message');
      el.textContent = text || '';
      el.className = 'message';
      if (mode) el.classList.add(mode);
      ui.lastActionMessageTs = Date.now();
    }

    function setBackgroundMessage(text, mode) {
      const el = byId('background_message');
      if (!el) return;
      el.textContent = text || '';
      el.className = 'message subtle';
      if (mode) el.classList.add(mode);
    }

    function setImageMessage(text, mode) {
      const el = byId('image_message');
      if (!el) return;
      el.textContent = text || '';
      el.className = 'message';
      if (mode) el.classList.add(mode);
    }

    function setModuleMessage(messageId, text, mode) {
      const el = byId(messageId);
      if (!el) return;
      el.textContent = text || '';
      el.className = 'message';
      if (mode) el.classList.add(mode);
    }

    function setButtonDisabled(buttonId, disabled) {
      const btn = byId(buttonId);
      if (!btn) return;
      btn.disabled = !!disabled;
    }

    function isAnyGeneralBusy() {
      return !!(
        ui.generalBusy.text ||
        ui.generalBusy.image ||
        ui.generalBusy.translation ||
        ui.generalBusy.voice
      );
    }

    function parseNullableIntText(text) {
      const raw = String(text || '').trim();
      if (!raw) return null;
      const value = parseInt(raw, 10);
      return Number.isFinite(value) ? value : null;
    }

    function parseLangList(text) {
      const parts = String(text || '')
        .replace(/\r/g, '\n')
        .replace(/,/g, '\n')
        .split('\n');
      const seen = {};
      const rows = [];
      for (let i = 0; i < parts.length; i += 1) {
        const item = parts[i].trim();
        if (!item) continue;
        const key = item.toLowerCase();
        if (seen[key]) continue;
        seen[key] = true;
        rows.push(item);
      }
      return rows;
    }

    function normalizeLangToken(value) {
      return String(value || '').trim().toLowerCase().replace(/_/g, '-');
    }

    function syncTranslationSourceLangByFolder() {
      const sourceFolderSelect = byId('module_trans_source_folder');
      const sourceLangSelect = byId('module_trans_source_lang');
      if (!sourceFolderSelect || !sourceLangSelect) return;
      const sourceFolder = normalizeLangToken(sourceFolderSelect.value || 'en');
      const mapped = SOURCE_LANG_CODE_BY_FOLDER[sourceFolder] || null;
      if (!mapped) return;
      const options = sourceLangSelect.options;
      for (let i = 0; i < options.length; i += 1) {
        if (String(options[i].value || '') === mapped) {
          sourceLangSelect.value = mapped;
          return;
        }
      }
    }

    function syncTranslationSourceFolderOptions(languages) {
      const select = byId('module_trans_source_folder');
      if (!select) return;
      const current = String(select.value || '').trim();
      const fallback = ['en', 'zh', 'ja', 'ko', 'fr', 'de', 'es', 'pt'];
      const pool = Array.isArray(languages) && languages.length ? languages : fallback;
      const seen = {};
      const rows = [];
      for (let i = 0; i < pool.length; i += 1) {
        const token = String(pool[i] || '').trim();
        if (!token) continue;
        const key = token.toLowerCase();
        if (seen[key]) continue;
        seen[key] = true;
        rows.push(token);
      }
      if (!rows.length) rows.push('en');

      select.innerHTML = '';
      for (let i = 0; i < rows.length; i += 1) {
        const option = document.createElement('option');
        option.value = rows[i];
        option.textContent = rows[i];
        select.appendChild(option);
      }

      if (current && rows.indexOf(current) >= 0) {
        select.value = current;
      } else if (rows.indexOf('en') >= 0) {
        select.value = 'en';
      } else {
        select.value = rows[0];
      }
      syncTranslationSourceLangByFolder();
    }

    function collectTranslationTargetLangs() {
      const container = byId('module_trans_target_list');
      const sourceFolder = normalizeLangToken((byId('module_trans_source_folder').value || '').trim());
      if (!container) return [];
      const checks = container.querySelectorAll('input[type="checkbox"][data-lang]');
      const seen = {};
      const rows = [];
      for (let i = 0; i < checks.length; i += 1) {
        const input = checks[i];
        if (!input.checked) continue;
        const token = String(input.getAttribute('data-lang') || '').trim();
        if (!token) continue;
        const key = token.toLowerCase();
        if (seen[key]) continue;
        if (normalizeLangToken(token) === sourceFolder) continue;
        seen[key] = true;
        rows.push(token);
      }
      return rows;
    }

    function updateTranslationStoryMeta(story) {
      const meta = byId('module_trans_story_meta');
      if (!meta) return;
      if (!ui.translatableStories.length) {
        meta.textContent = t('module.translation.story_no_available', 'No translatable story found.');
        return;
      }
      if (!story) {
        meta.textContent = tf('module.translation.story_count', {count: String(ui.translatableStories.length)}, 'Detected stories: {count}');
        return;
      }
      const langs = Array.isArray(story.languages) ? story.languages : [];
      const updated = story.updated_at ? isoToLocal(story.updated_at) : '-';
      meta.textContent = tf(
        'module.translation.story_selected_meta',
        {
          languages: langs.length ? langs.join(', ') : '-',
          updated: String(updated),
        },
        'Languages: {languages} | Updated: {updated}'
      );
    }

    function applySelectedTranslationStory() {
      const select = byId('module_trans_story_select');
      const storyRootInput = byId('module_trans_story_root');
      if (!select || !storyRootInput) return;
      const selectedRoot = String(select.value || '').trim();
      if (selectedRoot) {
        storyRootInput.value = selectedRoot;
      }

      let selectedStory = null;
      for (let i = 0; i < ui.translatableStories.length; i += 1) {
        const row = ui.translatableStories[i] || {};
        if (String(row.story_root || '') === selectedRoot) {
          selectedStory = row;
          break;
        }
      }

      const languages = selectedStory && Array.isArray(selectedStory.languages) ? selectedStory.languages : [];
      syncTranslationSourceFolderOptions(languages);
      updateTranslationStoryMeta(selectedStory);
    }

    function renderTranslatableStories(data, preferredRoot) {
      const select = byId('module_trans_story_select');
      if (!select) return;

      const keep = String(preferredRoot || select.value || byId('module_trans_story_root').value || '').trim();
      const items = Array.isArray(data && data.items) ? data.items : [];
      ui.translatableStories = items;

      select.innerHTML = '';
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = t('module.translation.story_select_placeholder', '-- Select a story book --');
      select.appendChild(placeholder);

      for (let i = 0; i < items.length; i += 1) {
        const item = items[i] || {};
        const root = String(item.story_root || '').trim();
        if (!root) continue;
        const langs = Array.isArray(item.languages) ? item.languages : [];
        const storyName = String(item.story_name || '').trim() || root.split('/').pop() || root;
        const option = document.createElement('option');
        option.value = root;
        option.textContent = langs.length ? (storyName + ' [' + langs.join(', ') + ']') : storyName;
        select.appendChild(option);
      }

      if (keep) {
        select.value = keep;
      }
      if (!select.value && select.options.length > 1) {
        select.selectedIndex = 1;
      }
      applySelectedTranslationStory();
    }

    async function fetchTranslatableStories(preferredRoot) {
      const meta = byId('module_trans_story_meta');
      if (meta) {
        meta.textContent = t('msg.loading_story_list', 'Loading available story books...');
      }
      try {
        const data = await apiGet('/api/stories/translatable?limit=120');
        renderTranslatableStories(data, preferredRoot);
      } catch (err) {
        ui.translatableStories = [];
        renderTranslatableStories({items: []}, preferredRoot);
        setModuleMessage('module_translation_message', String((err && err.message) || err || t('msg.story_list_load_failed', 'Failed to load story list.')), 'bad');
      }
    }

    function switchModuleStudio(studioName) {
      const name = String(studioName || 'story');
      ui.moduleStudio = name;

      const buttons = document.querySelectorAll('.module-tab-btn');
      for (let i = 0; i < buttons.length; i += 1) {
        const btn = buttons[i];
        if (btn.getAttribute('data-module-tab') === name) btn.classList.add('active');
        else btn.classList.remove('active');
      }

      const studios = ['story', 'image', 'translation', 'voice', 'general'];
      for (let i = 0; i < studios.length; i += 1) {
        const panel = byId('studio_' + studios[i]);
        if (!panel) continue;
        if (studios[i] === name) panel.classList.add('active');
        else panel.classList.remove('active');
      }

      if (name === 'translation') {
        fetchTranslatableStories();
      }
    }

    function syncModuleStoryInputMode() {
      const mode = byId('module_story_input_mode').value || 'preset';
      const disableCustom = mode !== 'custom';
      byId('module_story_prompt').disabled = disableCustom;
      byId('module_story_materials').disabled = disableCustom;
      const customGroup = byId('module_story_custom_group');
      const customMetaGroup = byId('module_story_custom_meta_group');
      if (customGroup) customGroup.style.display = disableCustom ? 'none' : 'grid';
      if (customMetaGroup) customMetaGroup.style.display = disableCustom ? 'none' : 'grid';
    }

    function collectStoryModulePayload() {
      const mode = byId('module_story_input_mode').value || 'preset';
      const isCustom = mode === 'custom';
      return {
        count: parseIntSafe(byId('module_story_count').value, 1),
        pages: parseIntSafe(byId('module_story_pages').value, 0),
        priority: byId('module_story_priority').value || 'normal',
        age: byId('module_story_age').value || null,
        category: byId('module_story_category').value || null,
        story_input_mode: mode,
        theme: isCustom
          ? ((byId('module_story_theme').value || '').trim() || null)
          : (byId('module_story_theme_select').value || null),
        subcategory: isCustom
          ? ((byId('module_story_subcategory').value || '').trim() || null)
          : (byId('module_story_subcategory_select').value || null),
        seed: parseNullableIntText(byId('module_story_seed').value),
        story_prompt: isCustom ? (byId('module_story_prompt').value || '').trim() : '',
        story_materials: isCustom ? (byId('module_story_materials').value || '').trim() : '',
        low_vram: byId('module_story_low_vram').checked,
      };
    }

    function collectTranslationModulePayload() {
      return {
        story_root: (byId('module_trans_story_root').value || '').trim() || null,
        source_folder: (byId('module_trans_source_folder').value || '').trim() || 'en',
        source_lang: (byId('module_trans_source_lang').value || '').trim() || 'eng_Latn',
        target_langs: collectTranslationTargetLangs(),
        beam_size: parseIntSafe(byId('module_trans_beam').value, 1),
        length_penalty: parseFloatSafe(byId('module_trans_length_penalty').value, 1.0),
        device: byId('module_trans_device').value || 'auto',
        dtype: byId('module_trans_dtype').value || 'float16',
        priority: byId('module_trans_priority').value || 'normal',
      };
    }

    function collectVoiceModulePayload() {
      return {
        story_root: (byId('module_voice_story_root').value || '').trim() || null,
        language: (byId('module_voice_language').value || '').trim() || null,
        speaker_wav: (byId('module_voice_speaker_wav').value || '').trim() || null,
        speaker_dir: (byId('module_voice_speaker_dir').value || '').trim() || null,
        page_start: parseNullableIntText(byId('module_voice_page_start').value),
        page_end: parseNullableIntText(byId('module_voice_page_end').value),
        gain: parseFloatSafe(byId('module_voice_gain').value, 1.0),
        speed: parseFloatSafe(byId('module_voice_speed').value, 1.0),
        device: byId('module_voice_device').value || 'auto',
        concat: byId('module_voice_concat').checked,
        keep_raw: byId('module_voice_keep_raw').checked,
        priority: byId('module_voice_priority').value || 'normal',
      };
    }

    function collectImageModulePayload() {
      const taskIds = [];
      for (let i = 0; i < ui.imageItems.length; i += 1) {
        const item = ui.imageItems[i] || {};
        const taskId = String(item.task_id || '');
        if (taskId && ui.imageSelectedTaskIds[taskId]) taskIds.push(taskId);
      }

      return {
        story_root: (byId('image_story_root').value || '').trim() || null,
        task_ids: taskIds,
        overrides: collectImageOverrides(),
        priority: byId('module_image_priority').value || 'normal',
      };
    }

    function renderModuleJobs(data) {
      const body = byId('module_jobs_body');
      const active = data && data.active_job ? data.active_job : null;
      const pending = Array.isArray(data && data.pending_jobs) ? data.pending_jobs : [];
      const history = Array.isArray(data && data.history) ? data.history : [];
      ui.moduleJobs = [];

      const rows = [];

      function pushRow(item, visualState) {
        if (!item) return;
        const state = String(visualState || item.status || 'queued').toLowerCase();
        const jobId = String(item.job_id || '');
        if (!jobId) return;
        if (isModuleJobHidden(jobId)) return;
        ui.moduleJobs.push(item);
        rows.push(
          '<tr>' +
            '<td>' + escapeHtml(jobId) + '</td>' +
            '<td>' + escapeHtml(String(item.job_type || '-')) + '</td>' +
            '<td><span class="result-pill ' + escapeHtml(state) + '">' + escapeHtml(localizeState(state)) + '</span></td>' +
            '<td>' + escapeHtml(t('module.priority.' + String(item.priority || 'normal'), String(item.priority || 'normal'))) + '</td>' +
            '<td>' + escapeHtml(String(item.story_root || '-')) + '</td>' +
            '<td>' +
              '<button class="btn ghost mini" data-action="module-detail" data-job-id="' + escapeHtml(jobId) + '">' + escapeHtml(t('btn.detail', 'Detail')) + '</button> ' +
              '<button class="btn danger mini" data-action="module-stop" data-job-id="' + escapeHtml(jobId) + '">' + escapeHtml(t('btn.stop_short', 'Stop')) + '</button>' +
            '</td>' +
          '</tr>'
        );
      }

      if (active) pushRow(active, 'running');
      for (let i = 0; i < pending.length; i += 1) pushRow(pending[i], 'queued');
      for (let i = 0; i < history.length; i += 1) pushRow(history[i], history[i] && history[i].status);

      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="6">' + escapeHtml(t('msg.no_module_jobs', 'No module jobs.')) + '</td></tr>';
        if (ui.moduleSelectedJobId) {
          ui.moduleSelectedJobId = '';
          renderModuleJobDetail({job: null});
        }
      } else {
        body.innerHTML = rows.join('');
        if (ui.moduleSelectedJobId && isModuleJobHidden(ui.moduleSelectedJobId)) {
          ui.moduleSelectedJobId = '';
          renderModuleJobDetail({job: null});
        }
      }
    }

    function renderModuleJobDetail(data) {
      const meta = byId('module_job_meta');
      const eventsBox = byId('module_job_events');
      const logsBox = byId('module_job_logs');

      const job = data && data.job ? data.job : null;
      if (!job) {
        meta.textContent = t('msg.no_module_job_selected', 'No module job selected.');
        eventsBox.innerHTML = '<div class="event-item">' + escapeHtml(t('msg.no_events', 'No events.')) + '</div>';
        logsBox.textContent = t('msg.no_module_logs', 'No module logs.');
        return;
      }

      ui.moduleSelectedJobId = String(job.job_id || '');
      meta.textContent =
        t('module.meta.job', 'Job') + '=' + String(job.job_id || '-') +
        ' | ' + t('module.meta.type', 'Type') + '=' + String(job.job_type || '-') +
        ' | ' + t('module.meta.status', 'Status') + '=' + localizeState(String(job.status || '-')) +
        ' | ' + t('module.meta.priority', 'Priority') + '=' + t('module.priority.' + String(job.priority || 'normal'), String(job.priority || '-'));

      const events = Array.isArray(data.events) ? data.events : [];
      if (!events.length) {
        eventsBox.innerHTML = '<div class="event-item">' + escapeHtml(t('msg.no_events', 'No events.')) + '</div>';
      } else {
        const html = [];
        for (let i = 0; i < events.length; i += 1) {
          const ev = events[i] || {};
          html.push(
            '<div class="event-item">' +
              '<b>' + escapeHtml(String(ev.event || '-')) + '</b>' +
              '<div class="meta">' + escapeHtml(isoToLocal(ev.ts)) + '</div>' +
              '<div class="meta">' + escapeHtml(JSON.stringify(ev.details || {})) + '</div>' +
            '</div>'
          );
        }
        eventsBox.innerHTML = html.join('');
      }

      const logs = Array.isArray(data.logs) ? data.logs : [];
      let blob = '';
      for (let i = 0; i < logs.length; i += 1) {
        const line = logs[i] || {};
        const ts = line.ts ? String(line.ts).slice(11, 19) : '--:--:--';
        blob += '[' + ts + '] ' + String(line.text || '') + '\n';
      }
      logsBox.textContent = blob || t('msg.no_module_logs', 'No module logs.');
    }

    async function fetchModuleJobs() {
      const data = await apiGet('/api/modules/jobs?limit=60');
      renderModuleJobs(data);
      return data;
    }

    async function clearModuleView() {
      let hiddenCount = 0;
      for (let i = 0; i < ui.moduleJobs.length; i += 1) {
        const item = ui.moduleJobs[i] || {};
        const jobId = String(item.job_id || '').trim();
        if (!jobId) continue;
        if (!isModuleJobHidden(jobId)) {
          ui.hiddenModuleJobs[jobId] = 1;
          hiddenCount += 1;
        }
      }

      if (hiddenCount <= 0) {
        setModuleMessage('module_jobs_message', t('msg.module_view_already_clean', 'Module panel is already clear.'), 'warn');
        return;
      }

      saveHiddenModuleJobs();
      if (ui.moduleSelectedJobId && isModuleJobHidden(ui.moduleSelectedJobId)) {
        ui.moduleSelectedJobId = '';
        renderModuleJobDetail({job: null});
      }

      setModuleMessage('module_jobs_message', tf('msg.cleared_module_view', {count: String(hiddenCount)}, 'Module panel cleared ({count} records hidden).'), 'ok');
      await fetchModuleJobs();
    }

    async function showAllModuleView() {
      ui.hiddenModuleJobs = {};
      saveHiddenModuleJobs();
      setModuleMessage('module_jobs_message', t('msg.module_view_restored', 'Module panel restored to show all records.'), 'ok');
      await fetchModuleJobs();
      if (ui.moduleSelectedJobId) {
        await fetchModuleJobDetail(ui.moduleSelectedJobId, {log_limit: 400, event_limit: 260});
      }
    }

    async function fetchModuleJobDetail(jobId, options) {
      const id = String(jobId || '').trim();
      if (!id) return null;
      const logLimit = _safeNumberOption(options, 'log_limit', 220);
      const eventLimit = _safeNumberOption(options, 'event_limit', 120);
      const data = await apiGet('/api/modules/job-detail?job_id=' + encodeURIComponent(id) + '&log_limit=' + String(logLimit) + '&event_limit=' + String(eventLimit));
      renderModuleJobDetail(data);
      return data;
    }

    function _safeNumberOption(options, key, fallback) {
      if (!options || typeof options !== 'object') return fallback;
      return parseIntSafe(options[key], fallback);
    }

    async function runModuleJob(jobType, payload, messageId, successPrefix) {
      setModuleMessage(messageId, t('msg.submitting_module_job', 'Submitting module job...'), 'ok');
      try {
        const data = await apiPost('/api/modules/run', {
          job_type: jobType,
          payload: payload,
        });
        const job = data.job || {};
        const jobId = String(job.job_id || '');
        ui.moduleSelectedJobId = jobId;
        setModuleMessage(messageId, jobId ? tf('msg.module_job_queued', {id: jobId}, 'Module job queued: {id}') : String(successPrefix || 'Module job queued'), 'ok');
        await fetchModuleJobs();
        if (jobId) await fetchModuleJobDetail(jobId, {log_limit: 320, event_limit: 180});
      } catch (err) {
        setModuleMessage(messageId, String((err && err.message) || err || t('msg.failed_run_module_job', 'Failed to run module job.')), 'bad');
      }
    }

    async function runStoryModuleJob() {
      await runModuleJob('story', collectStoryModulePayload(), 'module_story_message', 'Text module queued');
    }

    async function runTranslationModuleJob() {
      const payload = collectTranslationModulePayload();
      if (!payload.target_langs.length) {
        setModuleMessage('module_translation_message', t('msg.translation_targets_required', 'Please select at least one target language.'), 'warn');
        return;
      }
      await runModuleJob('translation', payload, 'module_translation_message', 'Translation module queued');
    }

    async function runVoiceModuleJob() {
      await runModuleJob('voice', collectVoiceModulePayload(), 'module_voice_message', 'Voice module queued');
    }

    async function runImageModuleJob() {
      const payload = collectImageModulePayload();
      await runModuleJob('image', payload, 'image_message', 'Image module queued');
    }

    async function refreshModuleJobsAfterGeneral(data) {
      await fetchModuleJobs();
      const jobId = data && data.module_job_id ? String(data.module_job_id) : '';
      if (jobId) {
        ui.moduleSelectedJobId = jobId;
        await fetchModuleJobDetail(jobId, {log_limit: 320, event_limit: 180});
      }
    }

    async function runGeneralTextTool() {
      if (isAnyGeneralBusy()) {
        setModuleMessage('general_message', t('msg.general_already_running', 'A request is still running. Please wait.'), 'warn');
        return;
      }
      const prompt = (byId('general_text_prompt').value || '').trim();
      if (!prompt) {
        setModuleMessage('general_message', t('msg.general_prompt_required', 'Please enter a prompt.'), 'warn');
        return;
      }
      ui.generalBusy.text = true;
      setButtonDisabled('btn_general_text_run', true);
      setModuleMessage('general_message', t('msg.general_running', 'Running request...'), 'ok');
      try {
        const data = await apiPost('/api/general/text', {
          prompt: prompt,
          system_prompt: (byId('general_text_system').value || '').trim() || 'You are a helpful assistant.',
          max_tokens: parseIntSafe(byId('general_text_max_tokens').value, 512),
          temperature: parseFloatSafe(byId('general_text_temperature').value, 0.85),
          top_p: parseFloatSafe(byId('general_text_top_p').value, 0.95),
          top_k: parseIntSafe(byId('general_text_top_k').value, 50),
        });
        byId('general_text_output').textContent = String(data.text || '');
        byId('general_text_meta').textContent = tf(
          'module.general.text.meta',
          {
            tokens: String(data.tokens == null ? '-' : data.tokens),
            model: String(data.model || '-'),
          },
          'tokens={tokens} | model={model}'
        );
        setModuleMessage('general_message', t('msg.general_text_done', 'General text generation completed.'), 'ok');
        await refreshModuleJobsAfterGeneral(data);
      } catch (err) {
        setModuleMessage('general_message', String((err && err.message) || err || t('msg.general_request_failed', 'General request failed.')), 'bad');
        try { await fetchModuleJobs(); } catch (_err) {}
      } finally {
        ui.generalBusy.text = false;
        setButtonDisabled('btn_general_text_run', false);
      }
    }

    async function runGeneralImageTool() {
      if (isAnyGeneralBusy()) {
        setModuleMessage('general_message', t('msg.general_already_running', 'A request is still running. Please wait.'), 'warn');
        return;
      }
      const prompt = (byId('general_image_prompt').value || '').trim();
      if (!prompt) {
        setModuleMessage('general_message', t('msg.general_prompt_required', 'Please enter a prompt.'), 'warn');
        return;
      }
      ui.generalBusy.image = true;
      setButtonDisabled('btn_general_image_run', true);
      setModuleMessage('general_message', t('msg.general_running', 'Running request...'), 'ok');
      try {
        const data = await apiPost('/api/general/image', {
          prompt: prompt,
          negative_prompt: (byId('general_image_negative').value || '').trim(),
          width: parseIntSafe(byId('general_image_width').value, 1024),
          height: parseIntSafe(byId('general_image_height').value, 768),
          steps: parseIntSafe(byId('general_image_steps').value, 40),
          guidance: parseFloatSafe(byId('general_image_guidance').value, 7.0),
          seed: parseNullableIntText(byId('general_image_seed').value),
          refiner_steps: parseNullableIntText(byId('general_image_refiner_steps').value),
          skip_refiner: byId('general_image_skip_refiner').checked,
          low_vram: byId('general_image_low_vram').checked,
        });
        const imagePath = String(data.image_path || '');
        if (imagePath) {
          const preview = byId('general_image_preview');
          preview.src = buildImageFileUrl(imagePath);
          preview.style.display = 'block';
        }
        byId('general_image_meta').textContent = tf(
          'module.general.image.meta',
          {
            path: imagePath || '-',
            seed: String(data.seed == null ? '-' : data.seed),
            width: String(data.width || '-'),
            height: String(data.height || '-'),
          },
          'path={path} | seed={seed} | {width}x{height}'
        );
        setModuleMessage('general_message', t('msg.general_image_done', 'General image generation completed.'), 'ok');
        await refreshModuleJobsAfterGeneral(data);
      } catch (err) {
        setModuleMessage('general_message', String((err && err.message) || err || t('msg.general_request_failed', 'General request failed.')), 'bad');
        try { await fetchModuleJobs(); } catch (_err) {}
      } finally {
        ui.generalBusy.image = false;
        setButtonDisabled('btn_general_image_run', false);
      }
    }

    async function runGeneralTranslationTool() {
      if (isAnyGeneralBusy()) {
        setModuleMessage('general_message', t('msg.general_already_running', 'A request is still running. Please wait.'), 'warn');
        return;
      }
      const text = (byId('general_trans_text').value || '').trim();
      if (!text) {
        setModuleMessage('general_message', t('msg.general_text_required', 'Please enter text.'), 'warn');
        return;
      }
      ui.generalBusy.translation = true;
      setButtonDisabled('btn_general_translation_run', true);
      setModuleMessage('general_message', t('msg.general_running', 'Running request...'), 'ok');
      try {
        const data = await apiPost('/api/general/translate', {
          text: text,
          source_lang: (byId('general_trans_source').value || '').trim() || 'en',
          target_lang: (byId('general_trans_target').value || '').trim() || 'zh-TW',
          beam_size: parseIntSafe(byId('general_trans_beam').value, 1),
          dtype: byId('general_trans_dtype').value || 'float16',
        });
        byId('general_trans_output').value = String(data.translated_text || '');
        byId('general_trans_meta').textContent = tf(
          'module.general.translation.meta',
          {
            source: String(data.source_lang || '-'),
            target: String(data.target_lang || '-'),
          },
          'source={source} -> target={target}'
        );
        setModuleMessage('general_message', t('msg.general_translation_done', 'General translation completed.'), 'ok');
        await refreshModuleJobsAfterGeneral(data);
      } catch (err) {
        setModuleMessage('general_message', String((err && err.message) || err || t('msg.general_request_failed', 'General request failed.')), 'bad');
        try { await fetchModuleJobs(); } catch (_err) {}
      } finally {
        ui.generalBusy.translation = false;
        setButtonDisabled('btn_general_translation_run', false);
      }
    }

    async function runGeneralVoiceTool() {
      if (isAnyGeneralBusy()) {
        setModuleMessage('general_message', t('msg.general_already_running', 'A request is still running. Please wait.'), 'warn');
        return;
      }
      const text = (byId('general_voice_text').value || '').trim();
      if (!text) {
        setModuleMessage('general_message', t('msg.general_voice_text_required', 'Please enter narration text.'), 'warn');
        return;
      }
      ui.generalBusy.voice = true;
      setButtonDisabled('btn_general_voice_run', true);
      setModuleMessage('general_message', t('msg.general_running', 'Running request...'), 'ok');
      try {
        const data = await apiPost('/api/general/voice', {
          text: text,
          language: (byId('general_voice_language').value || '').trim() || 'en',
          speaker_wav: (byId('general_voice_speaker_wav').value || '').trim() || null,
          speed: parseFloatSafe(byId('general_voice_speed').value, 1.0),
          temperature: parseFloatSafe(byId('general_voice_temperature').value, 0.7),
        });
        const audioPath = String(data.audio_path || '');
        if (audioPath) {
          const audio = byId('general_voice_audio');
          audio.src = buildImageFileUrl(audioPath);
          audio.load();
        }
        if (data.speaker_wav) {
          byId('general_voice_speaker_wav').value = String(data.speaker_wav);
        }
        byId('general_voice_meta').textContent = tf(
          'module.general.voice.meta',
          {
            audio: audioPath || '-',
            speaker: String(data.speaker_wav || '-'),
          },
          'audio={audio} | speaker={speaker}'
        );
        setModuleMessage('general_message', t('msg.general_voice_done', 'General voice generation completed.'), 'ok');
        await refreshModuleJobsAfterGeneral(data);
      } catch (err) {
        setModuleMessage('general_message', String((err && err.message) || err || t('msg.general_request_failed', 'General request failed.')), 'bad');
        try { await fetchModuleJobs(); } catch (_err) {}
      } finally {
        ui.generalBusy.voice = false;
        setButtonDisabled('btn_general_voice_run', false);
      }
    }

    async function stopModuleJob(jobId) {
      const id = String(jobId || ui.moduleSelectedJobId || '').trim();
      if (!id) {
        setModuleMessage('module_jobs_message', t('msg.select_module_job_first', 'Select a module job first.'), 'warn');
        return;
      }
      try {
        await apiPost('/api/modules/stop', {job_id: id});
        if (ui.moduleSelectedJobId === id) {
          setModuleMessage('module_jobs_message', tf('msg.stop_requested_for_module_job', {id: id}, 'Stop requested for module job {id}'), 'warn');
        }
        await fetchModuleJobs();
        await fetchModuleJobDetail(id, {log_limit: 320, event_limit: 180});
      } catch (err) {
        setModuleMessage('module_jobs_message', String((err && err.message) || err || t('msg.failed_stop_module_job', 'Failed to stop module job.')), 'bad');
      }
    }

    function buildImageFileUrl(path) {
      return '/api/images/file?path=' + encodeURIComponent(String(path || ''));
    }

    function findImageByTaskId(taskId) {
      if (!taskId) return null;
      for (let i = 0; i < ui.imageItems.length; i += 1) {
        const item = ui.imageItems[i] || {};
        if (String(item.task_id || '') === String(taskId)) return item;
      }
      return null;
    }

    function populateImageDetail(item) {
      if (!item) {
        byId('image_detail_meta').textContent = t('msg.none_selected', 'None selected.');
        byId('image_positive_prompt').value = '';
        byId('image_negative_prompt').value = '';
        byId('image_width').value = '';
        byId('image_height').value = '';
        byId('image_steps').value = '';
        byId('image_guidance').value = '';
        byId('image_seed').value = '';
        byId('image_refiner_steps').value = '';
        byId('image_skip_refiner').checked = false;
        return;
      }
      byId('image_detail_meta').textContent = tf(
        'module.meta.image_selected',
        {
          task: String(item.task_id || '-'),
          type: String(item.task_type || '-'),
          story: String(item.story_root || '-'),
        },
        'Task={task} | Type={type} | Story={story}'
      );
      byId('image_positive_prompt').value = String(item.positive_prompt || '');
      byId('image_negative_prompt').value = String(item.negative_prompt || '');
      byId('image_width').value = String(item.width || '');
      byId('image_height').value = String(item.height || '');
      byId('image_steps').value = String(item.steps || '');
      byId('image_guidance').value = String(item.guidance || '');
      byId('image_seed').value = item.seed == null ? '' : String(item.seed);
      byId('image_refiner_steps').value = item.refiner_steps == null ? '' : String(item.refiner_steps);
      byId('image_skip_refiner').checked = item.skip_refiner === true;
    }

    function collectImageOverrides() {
      function parseNullableInt(text) {
        const raw = String(text || '').trim();
        if (!raw) return null;
        const v = parseInt(raw, 10);
        return Number.isFinite(v) ? v : null;
      }

      function parseNullableFloat(text) {
        const raw = String(text || '').trim();
        if (!raw) return null;
        const v = parseFloat(raw);
        return Number.isFinite(v) ? v : null;
      }

      return {
        positive_prompt: (byId('image_positive_prompt').value || '').trim() || null,
        negative_prompt: (byId('image_negative_prompt').value || '').trim() || null,
        width: parseNullableInt(byId('image_width').value),
        height: parseNullableInt(byId('image_height').value),
        steps: parseNullableInt(byId('image_steps').value),
        guidance: parseNullableFloat(byId('image_guidance').value),
        seed: parseNullableInt(byId('image_seed').value),
        refiner_steps: parseNullableInt(byId('image_refiner_steps').value),
        skip_refiner: byId('image_skip_refiner').checked,
      };
    }

    function renderImageGallery(data) {
      const gallery = byId('image_gallery');
      const items = Array.isArray(data && data.items) ? data.items : [];
      ui.imageItems = items;

      if (data && data.story_root) {
        ui.imageStoryRoot = String(data.story_root);
        if (!(byId('image_story_root').value || '').trim()) {
          byId('image_story_root').value = ui.imageStoryRoot;
        }
      }

      if (!items.length) {
        gallery.innerHTML = '<div class="list-item">' + escapeHtml(t('msg.no_generated_images', 'No generated images yet.')) + '</div>';
        populateImageDetail(null);
        return;
      }

      const tiles = [];
      for (let i = 0; i < items.length; i += 1) {
        const item = items[i] || {};
        const taskId = String(item.task_id || '');
        const checked = ui.imageSelectedTaskIds[taskId] ? ' checked' : '';
        const updated = item.updated_at ? isoToLocal(item.updated_at) : '-';
        tiles.push(
          '<div class="image-tile">' +
            '<img loading="lazy" src="' + escapeHtml(buildImageFileUrl(item.image_path || '')) + '" alt="' + escapeHtml(taskId) + '" />' +
            '<div class="image-meta">' +
              '<div><b>' + escapeHtml(String(item.task_type || '-')) + '</b> ' + escapeHtml(String(item.task_name || '')) + '</div>' +
              '<div>' + escapeHtml(updated) + '</div>' +
            '</div>' +
            '<label class="image-select"><input type="checkbox" data-action="image-select" data-task-id="' + escapeHtml(taskId) + '"' + checked + ' /> ' + escapeHtml(t('btn.select', 'Select')) + '</label>' +
            '<button class="btn ghost mini" type="button" data-action="image-edit" data-task-id="' + escapeHtml(taskId) + '">' + escapeHtml(t('btn.inspect', 'Inspect')) + '</button>' +
          '</div>'
        );
      }
      gallery.innerHTML = tiles.join('');

      if (ui.imageDetailTaskId) {
        populateImageDetail(findImageByTaskId(ui.imageDetailTaskId));
      }
    }

    async function fetchImages() {
      const storyRoot = (byId('image_story_root').value || '').trim();
      const query = storyRoot
        ? '?story_root=' + encodeURIComponent(storyRoot) + '&limit=240'
        : '?limit=240';
      const data = await apiGet('/api/images/items' + query);
      renderImageGallery(data);
      return data;
    }

    async function regenerateSelectedImages() {
      const selected = [];
      for (let i = 0; i < ui.imageItems.length; i += 1) {
        const item = ui.imageItems[i] || {};
        const taskId = String(item.task_id || '');
        if (ui.imageSelectedTaskIds[taskId]) selected.push(item);
      }
      if (!selected.length) {
        setImageMessage(t('msg.select_at_least_one_image', 'Please select at least one image item.'), 'warn');
        return;
      }
      setImageMessage(t('msg.regenerating_selected_images', 'Regenerating selected images...'), 'ok');
      try {
        const data = await apiPost('/api/images/regenerate', {items: selected});
        const okCount = (data.results || []).filter(function (x) { return x && x.ok; }).length;
        setImageMessage(tf('msg.regenerated_images', {ok: String(okCount), total: String(selected.length)}, 'Regenerated {ok}/{total} images.'), okCount === selected.length ? 'ok' : 'warn');
        await fetchImages();
      } catch (err) {
        setImageMessage(String((err && err.message) || err || t('msg.failed_regenerate_selected_images', 'Failed to regenerate selected images.')), 'bad');
      }
    }

    async function regenerateDetailImage() {
      const taskId = ui.imageDetailTaskId;
      const item = findImageByTaskId(taskId);
      if (!item) {
        setImageMessage(t('msg.select_image_for_regen', 'Select one image to regenerate with edits.'), 'warn');
        return;
      }
      const overrides = collectImageOverrides();
      setImageMessage(t('msg.regenerating_image_with_edits', 'Regenerating selected image with edited parameters...'), 'ok');
      try {
        const data = await apiPost('/api/images/regenerate', {
          items: [item],
          overrides: overrides,
        });
        const result = (data.results || [])[0] || {};
        if (result.ok) {
          setImageMessage(t('msg.image_regenerated_successfully', 'Image regenerated successfully.'), 'ok');
        } else {
          setImageMessage(String(result.error || t('msg.image_regeneration_failed', 'Image regeneration failed.')), 'bad');
        }
        await fetchImages();
      } catch (err) {
        setImageMessage(String((err && err.message) || err || t('msg.failed_regenerate_image', 'Failed to regenerate image.')), 'bad');
      }
    }

    function payloadFromForm() {
      const seedRaw = byId('seed').value.trim();
      const inputMode = byId('story_input_mode').value || 'preset';
      const isCustom = inputMode === 'custom';
      return {
        count: parseIntSafe(byId('count').value, 1),
        max_retries: parseIntSafe(byId('max_retries').value, 1),
        priority: byId('priority').value || 'normal',
        age: byId('age').value || null,
        category: byId('category').value || null,
        story_input_mode: inputMode,
        theme: isCustom
          ? ((byId('theme_custom').value || '').trim() || null)
          : (byId('theme').value || null),
        subcategory: isCustom
          ? ((byId('subcategory_custom').value || '').trim() || null)
          : (byId('subcategory').value || null),
        pages: parseIntSafe(byId('pages').value, 0),
        seed: seedRaw ? parseIntSafe(seedRaw, 0) : null,
        story_prompt: isCustom ? (byId('story_prompt').value || '').trim() : '',
        story_materials: isCustom ? (byId('story_materials').value || '').trim() : '',
        speaker_wav: (byId('speaker_wav').value || '').trim() || null,
        speaker_dir: (byId('speaker_dir').value || '').trim() || null,
        photo_enabled: byId('photo_enabled').checked,
        translation_enabled: byId('translation_enabled').checked,
        voice_enabled: byId('voice_enabled').checked,
        verify_enabled: byId('verify_enabled').checked,
        low_vram: byId('low_vram').checked,
        strict_translation: byId('strict_translation').checked,
        strict_voice: byId('strict_voice').checked,
      };
    }

    function setFormFromPayload(payload) {
      const p = payload || {};
      byId('count').value = String(parseIntSafe(p.count, 1));
      byId('max_retries').value = String(parseIntSafe(p.max_retries, 1));
      byId('priority').value = p.priority || 'normal';
      byId('age').value = p.age || '';
      byId('category').value = p.category || '';
      byId('story_input_mode').value = p.story_input_mode || 'preset';
      if ((p.story_input_mode || 'preset') === 'custom') {
        byId('theme').value = '';
        byId('subcategory').value = '';
        byId('theme_custom').value = p.theme || '';
        byId('subcategory_custom').value = p.subcategory || '';
      } else {
        byId('theme').value = p.theme || '';
        byId('subcategory').value = p.subcategory || '';
        byId('theme_custom').value = '';
        byId('subcategory_custom').value = '';
      }
      byId('pages').value = String(parseIntSafe(p.pages, 0));
      byId('seed').value = p.seed == null ? '' : String(parseIntSafe(p.seed, 0));
      byId('story_prompt').value = p.story_prompt || '';
      byId('story_materials').value = p.story_materials || '';
      byId('speaker_wav').value = p.speaker_wav || '';
      byId('speaker_dir').value = p.speaker_dir || '';
      byId('photo_enabled').checked = p.photo_enabled !== false;
      byId('translation_enabled').checked = p.translation_enabled !== false;
      byId('voice_enabled').checked = p.voice_enabled !== false;
      byId('verify_enabled').checked = p.verify_enabled !== false;
      byId('low_vram').checked = p.low_vram !== false;
      byId('strict_translation').checked = p.strict_translation !== false;
      byId('strict_voice').checked = p.strict_voice !== false;
      syncStoryInputMode();
    }

    function syncStoryInputMode() {
      const mode = byId('story_input_mode').value || 'preset';
      const disabled = mode !== 'custom';
      byId('story_prompt').disabled = disabled;
      byId('story_materials').disabled = disabled;
      const promptGroup = byId('story_prompt_group');
      const customGroup = byId('story_custom_group');
      const customMetaGroup = byId('custom_meta_group');
      if (promptGroup) promptGroup.style.display = disabled ? 'none' : 'grid';
      if (customGroup) customGroup.style.display = disabled ? 'none' : 'grid';
      if (customMetaGroup) customMetaGroup.style.display = disabled ? 'none' : 'grid';
      if (disabled) {
        byId('story_prompt').placeholder = t('placeholder.story_prompt_preset', 'Preset mode: direct generation (no conversion layer).');
        byId('story_materials').placeholder = t('placeholder.story_materials_preset', 'Preset mode: direct generation (no conversion layer).');
      } else {
        byId('story_prompt').placeholder = t('placeholder.story_prompt_custom', 'Use concise requirements: mood, values, characters, conflict, ending style.');
        byId('story_materials').placeholder = t('placeholder.story_materials_custom', 'Paste notes, outlines, facts, classroom material, or family context.');
      }
    }

    function mergeFloat32(chunks) {
      let total = 0;
      for (let i = 0; i < chunks.length; i += 1) total += chunks[i].length;
      const out = new Float32Array(total);
      let offset = 0;
      for (let i = 0; i < chunks.length; i += 1) {
        out.set(chunks[i], offset);
        offset += chunks[i].length;
      }
      return out;
    }

    function encodeWav(floatData, sampleRate) {
      const buffer = new ArrayBuffer(44 + floatData.length * 2);
      const view = new DataView(buffer);

      function writeString(offset, text) {
        for (let i = 0; i < text.length; i += 1) {
          view.setUint8(offset + i, text.charCodeAt(i));
        }
      }

      writeString(0, 'RIFF');
      view.setUint32(4, 36 + floatData.length * 2, true);
      writeString(8, 'WAVE');
      writeString(12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeString(36, 'data');
      view.setUint32(40, floatData.length * 2, true);

      let offset = 44;
      for (let i = 0; i < floatData.length; i += 1) {
        const s = Math.max(-1, Math.min(1, floatData[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
        offset += 2;
      }
      return new Blob([buffer], {type: 'audio/wav'});
    }

    async function startRecording() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({audio: true});
        const AudioContextRef = window.AudioContext || window.webkitAudioContext;
        const ctx = new AudioContextRef();
        const source = ctx.createMediaStreamSource(stream);
        const processor = ctx.createScriptProcessor(4096, 1, 1);

        ui.recordChunks = [];
        ui.recordSampleRate = ctx.sampleRate || 16000;
        ui.recordBlob = null;

        processor.onaudioprocess = function (evt) {
          const channel = evt.inputBuffer.getChannelData(0);
          ui.recordChunks.push(new Float32Array(channel));
        };

        source.connect(processor);
        processor.connect(ctx.destination);

        ui.recordStream = stream;
        ui.recordContext = ctx;
        ui.recordSource = source;
        ui.recordProcessor = processor;

        byId('btn_record_start').disabled = true;
        byId('btn_record_stop').disabled = false;
        byId('btn_record_save').disabled = true;
        setMessage(t('msg.recording_read_script', 'Recording... please read the script naturally.'), 'ok');
      } catch (err) {
        setMessage(String((err && err.message) || err || t('msg.microphone_access_failed', 'Microphone access failed.')), 'bad');
      }
    }

    function stopRecording() {
      if (!ui.recordContext || !ui.recordProcessor || !ui.recordStream) return;
      try {
        ui.recordProcessor.disconnect();
        ui.recordSource.disconnect();
        const tracks = ui.recordStream.getTracks();
        for (let i = 0; i < tracks.length; i += 1) tracks[i].stop();
        ui.recordContext.close();
      } catch (_err) {
      }

      ui.recordProcessor = null;
      ui.recordSource = null;
      ui.recordStream = null;
      ui.recordContext = null;

      const merged = mergeFloat32(ui.recordChunks || []);
      ui.recordBlob = encodeWav(merged, ui.recordSampleRate || 16000);
      const preview = byId('record_preview');
      preview.src = URL.createObjectURL(ui.recordBlob);

      byId('btn_record_start').disabled = false;
      byId('btn_record_stop').disabled = true;
      byId('btn_record_save').disabled = !ui.recordBlob;
      setMessage(t('msg.recording_captured', 'Recording captured. You can preview and save it as speaker WAV.'), 'ok');
    }

    async function saveRecordingAsSpeaker() {
      if (!ui.recordBlob) {
        setMessage(t('msg.no_recording_available', 'No recording available.'), 'warn');
        return;
      }
      const reader = new FileReader();
      reader.onload = async function () {
        try {
          const dataUrl = String(reader.result || '');
          const base64 = dataUrl.split(',')[1] || '';
          const scriptText = (byId('voice_script').value || '').trim();
          const result = await apiPost('/api/voice/recordings/save', {
            wav_base64: base64,
            sample_rate: ui.recordSampleRate || 16000,
            script_text: scriptText,
          });
          if (result && result.path) {
            byId('speaker_wav').value = String(result.path);
            setMessage(tf('msg.speaker_sample_saved', {path: String(result.path)}, 'Speaker sample saved: {path}'), 'ok');
          }
        } catch (err) {
          setMessage(String((err && err.message) || err || t('msg.failed_save_recording', 'Failed to save recording.')), 'bad');
        }
      };
      reader.readAsDataURL(ui.recordBlob);
    }

    async function startModuleRecording() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({audio: true});
        const AudioContextRef = window.AudioContext || window.webkitAudioContext;
        const ctx = new AudioContextRef();
        const source = ctx.createMediaStreamSource(stream);
        const processor = ctx.createScriptProcessor(4096, 1, 1);

        ui.moduleRecordChunks = [];
        ui.moduleRecordSampleRate = ctx.sampleRate || 16000;
        ui.moduleRecordBlob = null;

        processor.onaudioprocess = function (evt) {
          const channel = evt.inputBuffer.getChannelData(0);
          ui.moduleRecordChunks.push(new Float32Array(channel));
        };

        source.connect(processor);
        processor.connect(ctx.destination);

        ui.moduleRecordStream = stream;
        ui.moduleRecordContext = ctx;
        ui.moduleRecordSource = source;
        ui.moduleRecordProcessor = processor;

        byId('btn_module_record_start').disabled = true;
        byId('btn_module_record_stop').disabled = false;
        byId('btn_module_record_save').disabled = true;
        setModuleMessage('module_voice_message', t('msg.recording_read_script', 'Recording... please read the script naturally.'), 'ok');
      } catch (err) {
        setModuleMessage('module_voice_message', String((err && err.message) || err || t('msg.microphone_access_failed', 'Microphone access failed.')), 'bad');
      }
    }

    function stopModuleRecording() {
      if (!ui.moduleRecordContext || !ui.moduleRecordProcessor || !ui.moduleRecordStream) return;
      try {
        ui.moduleRecordProcessor.disconnect();
        ui.moduleRecordSource.disconnect();
        const tracks = ui.moduleRecordStream.getTracks();
        for (let i = 0; i < tracks.length; i += 1) tracks[i].stop();
        ui.moduleRecordContext.close();
      } catch (_err) {
      }

      ui.moduleRecordProcessor = null;
      ui.moduleRecordSource = null;
      ui.moduleRecordStream = null;
      ui.moduleRecordContext = null;

      const merged = mergeFloat32(ui.moduleRecordChunks || []);
      ui.moduleRecordBlob = encodeWav(merged, ui.moduleRecordSampleRate || 16000);
      const preview = byId('module_record_preview');
      preview.src = URL.createObjectURL(ui.moduleRecordBlob);
      preview.style.display = 'block';

      byId('btn_module_record_start').disabled = false;
      byId('btn_module_record_stop').disabled = true;
      byId('btn_module_record_save').disabled = !ui.moduleRecordBlob;
      setModuleMessage('module_voice_message', t('msg.recording_captured', 'Recording captured. You can preview and save it as speaker WAV.'), 'ok');
    }

    async function saveModuleRecordingAsSpeaker() {
      if (!ui.moduleRecordBlob) {
        setModuleMessage('module_voice_message', t('msg.no_recording_available', 'No recording available.'), 'warn');
        return;
      }
      const reader = new FileReader();
      reader.onload = async function () {
        try {
          const dataUrl = String(reader.result || '');
          const base64 = dataUrl.split(',')[1] || '';
          const scriptText = (byId('module_voice_record_script').value || '').trim();
          const result = await apiPost('/api/voice/recordings/save', {
            wav_base64: base64,
            sample_rate: ui.moduleRecordSampleRate || 16000,
            script_text: scriptText,
          });
          if (result && result.path) {
            byId('module_voice_speaker_wav').value = String(result.path);
            setModuleMessage('module_voice_message', tf('msg.speaker_sample_saved', {path: String(result.path)}, 'Speaker sample saved: {path}'), 'ok');
          }
        } catch (err) {
          setModuleMessage('module_voice_message', String((err && err.message) || err || t('msg.failed_save_recording', 'Failed to save recording.')), 'bad');
        }
      };
      reader.readAsDataURL(ui.moduleRecordBlob);
    }

    function saveLocalForm() {
      localStorage.setItem(STORE_KEY, JSON.stringify(payloadFromForm()));
      setMessage(t('msg.saved_local_profile', 'Saved local form profile.'), 'ok');
    }

    function loadLocalForm() {
      const raw = localStorage.getItem(STORE_KEY);
      if (!raw) return;
      try {
        setFormFromPayload(JSON.parse(raw));
      } catch (_err) {
        localStorage.removeItem(STORE_KEY);
      }
    }

    function applyPreset(name) {
      const payload = payloadFromForm();
      if (name === 'speed') {
        payload.max_retries = 0;
        payload.priority = 'normal';
        payload.translation_enabled = false;
        payload.voice_enabled = false;
        payload.verify_enabled = true;
        payload.low_vram = true;
        payload.strict_translation = false;
        payload.strict_voice = false;
      } else if (name === 'quality') {
        payload.max_retries = 2;
        payload.priority = 'high';
        payload.translation_enabled = true;
        payload.voice_enabled = true;
        payload.verify_enabled = true;
        payload.low_vram = false;
        payload.strict_translation = true;
        payload.strict_voice = true;
      } else {
        payload.max_retries = 1;
        payload.priority = 'normal';
        payload.translation_enabled = true;
        payload.voice_enabled = true;
        payload.verify_enabled = true;
        payload.low_vram = true;
        payload.strict_translation = true;
        payload.strict_voice = true;
      }
      setFormFromPayload(payload);
      setMessage(tf('msg.preset_applied', {name: name}, 'Preset applied: {name}'), 'ok');
    }

    function setStatePill(text, state) {
      const el = byId('pill_state');
      el.textContent = localizeState(text);
      el.className = 'pill';
      if (state) el.classList.add(state);
    }

    function updatePreEvalPanel(preEvaluation, currentStage) {
      const panel = byId('pre_eval_panel');
      if (!panel) return;

      const payload = preEvaluation && typeof preEvaluation === 'object' ? preEvaluation : {};
      const metrics = payload.metrics && typeof payload.metrics === 'object' ? payload.metrics : {};
      const stageText = String(currentStage || '').toLowerCase();

      let state = String(payload.state || '').trim().toLowerCase();
      if (!state) {
        state = stageText.indexOf('pre_eval') >= 0 ? 'running' : 'idle';
      }

      const statePill = byId('pre_eval_state');
      if (statePill) {
        statePill.textContent = localizeState(state);
        statePill.className = 'pill';
        if (state) statePill.classList.add(state);
      }

      const overallScore = Number(payload.overall_score);
      const coherenceScore = Number(metrics.coherence);
      const entityScore = Number(metrics.entity_consistency);

      const scoreEl = byId('pre_eval_score');
      if (scoreEl) scoreEl.textContent = Number.isFinite(overallScore) ? overallScore.toFixed(2) : '-';
      const coherenceEl = byId('pre_eval_coherence');
      if (coherenceEl) coherenceEl.textContent = Number.isFinite(coherenceScore) ? coherenceScore.toFixed(2) : '-';
      const entityEl = byId('pre_eval_entity');
      if (entityEl) entityEl.textContent = Number.isFinite(entityScore) ? entityScore.toFixed(2) : '-';

      const policyEl = byId('pre_eval_policy');
      if (policyEl) {
        policyEl.textContent = payload.policy ? String(payload.policy) : '-';
      }

      const gateEl = byId('pre_eval_gate');
      if (gateEl) {
        if (payload.error) {
          gateEl.textContent = String(payload.error);
        } else if (payload.gate_message) {
          gateEl.textContent = String(payload.gate_message);
        } else if (state === 'running') {
          gateEl.textContent = t('msg.pre_eval_running', 'Pre-evaluation running...');
        } else if (state === 'completed') {
          gateEl.textContent = t('msg.pre_eval_completed', 'Pre-evaluation completed.');
        } else if (state === 'degraded') {
          gateEl.textContent = t('msg.pre_eval_degraded', 'Pre-evaluation completed with warning.');
        } else if (state === 'blocked') {
          gateEl.textContent = t('msg.pre_eval_blocked', 'Pre-evaluation blocked remaining stages.');
        } else {
          gateEl.textContent = t('msg.pre_eval_waiting', 'Waiting for pre-evaluation...');
        }
      }
    }

    function updateHeaderKpis(statusData, capacityData) {
      const runner = statusData && statusData.runner ? statusData.runner : {};
      const state = String(runner.state || (statusData && statusData.running ? 'running' : 'idle'));
      byId('kpi_system_state').textContent = localizeState(state);
      byId('kpi_queue_depth').textContent = String(statusData && Number.isFinite(Number(statusData.queue_depth)) ? statusData.queue_depth : 0);
      byId('kpi_success_rate').textContent = toPercent(capacityData ? capacityData.success_rate_pct : 0);
      byId('kpi_avg_duration').textContent = formatDuration(capacityData ? capacityData.avg_duration_sec : null);
      const usd = capacityData ? parseFloatSafe(capacityData.gpu_cost_usd, 0) : 0;
      byId('kpi_gpu_cost').textContent = '$' + usd.toFixed(2);
    }

    function renderStatus(data) {
      ui.latestStatus = data;
      const runner = data.runner || {};
      const state = String(runner.state || (data.running ? 'running' : 'idle')).toLowerCase();
      setStatePill(state, state);
      updatePreEvalPanel(runner.pre_evaluation, runner.current_stage);

      byId('pill_book').textContent = t('meta.book', 'book') + ': ' + String(runner.current_book == null ? '-' : runner.current_book);
      byId('pill_stage').textContent = t('meta.stage', 'stage') + ': ' + String(runner.current_stage || '-');

      const total = parseIntSafe(runner.total_books, 0);
      const completed = parseIntSafe(runner.completed_books, 0);
      const success = parseIntSafe(runner.success_books, 0);
      const failed = parseIntSafe(runner.failed_books, 0);
      const remaining = Math.max(0, total - completed);
      const stageText = String(runner.current_stage || '-');
      const successRate = completed > 0 ? ((success / completed) * 100) : 0;

      let progress = parseFloatSafe(data.progress_pct, Number.NaN);
      if (!Number.isFinite(progress)) {
        progress = total > 0 ? (completed / total) * 100 : 0;
      }
      progress = Math.max(0, Math.min(100, progress));
      byId('progress_fill').style.width = String(progress) + '%';
      byId('progress_label').textContent = progress.toFixed(1) + '%';
      byId('progress_detail').textContent = tf(
        'overview.progress.detail',
        {
          done: String(completed),
          total: String(total),
          remaining: String(remaining),
        },
        '{done}/{total} completed | {remaining} remaining'
      );
      byId('progress_badge_books').textContent = tf(
        'overview.progress.books',
        {done: String(completed), total: String(total)},
        'Books {done}/{total}'
      );
      byId('progress_badge_remaining').textContent = tf(
        'overview.progress.remaining',
        {count: String(remaining)},
        'Remaining {count}'
      );
      byId('progress_badge_success').textContent = tf(
        'overview.progress.success_rate',
        {pct: successRate.toFixed(1)},
        'Success {pct}%'
      );
      byId('progress_badge_stage').textContent = tf(
        'overview.progress.stage',
        {stage: stageText},
        'Stage {stage}'
      );

      const updatedAgo = data.updated_ago_sec;
      byId('updated_label').textContent = updatedAgo == null
        ? (t('meta.updated', 'updated') + ': -')
        : (t('meta.updated', 'updated') + ': ' + String(Math.round(updatedAgo)) + 's ago');

      byId('metric_total').textContent = String(total);
      byId('metric_completed').textContent = String(completed);
      byId('metric_success').textContent = String(success);
      byId('metric_failed').textContent = String(failed);
      byId('metric_elapsed').textContent = formatDuration(data.elapsed_sec);
      byId('metric_eta').textContent = formatDuration(data.eta_sec);

      byId('meta_run_id').textContent = String(data.run_id || '-');
      byId('meta_pid').textContent = data.pid == null ? '-' : String(data.pid);
      byId('meta_exit_code').textContent = data.exit_code == null ? '-' : String(data.exit_code);
      byId('meta_queue_depth').textContent = String(data.queue_depth || 0);

      byId('raw_status').textContent = JSON.stringify(data, null, 2);

      const startDisabled = Boolean(data.running) && (data.queue_depth || 0) >= 1;
      byId('btn_start').disabled = startDisabled;
      byId('btn_stop').disabled = !Boolean(data.running);

      const currentRunId = data.run_id || null;
      if (currentRunId !== ui.activeLogRunId) {
        ui.activeLogRunId = currentRunId;
        const opsLogs = byId('log_output');
        if (opsLogs) opsLogs.textContent = '';
        const overviewLogs = byId('overview_log_output');
        if (overviewLogs) {
          overviewLogs.textContent = currentRunId ? '' : t('msg.no_live_logs', 'No active run logs yet.');
        }
        ui.logCursor = Number(data.log_next_seq || 0);
      }

      if (data.last_error) {
        setMessage(String(data.last_error), 'warn');
      }
    }

    function appendLogs(lines) {
      if (!Array.isArray(lines) || !lines.length) return;
      const box = byId('log_output');
      const overviewBox = byId('overview_log_output');
      if (!box && !overviewBox) return;
      let chunk = '';
      for (let i = 0; i < lines.length; i += 1) {
        const line = lines[i] || {};
        const ts = line.ts ? String(line.ts).slice(11, 19) : '--:--:--';
        const txt = line.text ? String(line.text) : '';
        chunk += '[' + ts + '] ' + txt + '\n';
      }
      if (box) {
        box.textContent += chunk;
        if (box.textContent.length > 400000) {
          box.textContent = box.textContent.slice(-260000);
        }
      }

      if (overviewBox) {
        overviewBox.textContent += chunk;
        const rows = overviewBox.textContent.split('\n');
        if (rows.length > 260) {
          overviewBox.textContent = rows.slice(rows.length - 260).join('\n');
        }
        overviewBox.scrollTop = overviewBox.scrollHeight;
      }

      const autoScroll = byId('log_autoscroll');
      if (box && autoScroll && autoScroll.checked) {
        box.scrollTop = box.scrollHeight;
      }
    }

    function renderHistory(items) {
      ui.historyRows = Array.isArray(items) ? items : [];
      const body = byId('history_body');
      if (!ui.historyRows.length) {
        body.innerHTML = '<tr><td colspan="6">' + escapeHtml(t('msg.no_run_history', 'No run history yet.')) + '</td></tr>';
      } else {
        const rows = [];
        for (let i = 0; i < ui.historyRows.length; i += 1) {
          const item = ui.historyRows[i] || {};
          const state = String(item.state || 'unknown').toLowerCase();
          const cfg = item.config || {};
          const cfgText = [
            t('meta.count', 'count') + '=' + String(cfg.count ?? '-'),
            t('meta.retry', 'retry') + '=' + String(cfg.max_retries ?? '-'),
            t('meta.category', 'category') + '=' + String(cfg.category || 'auto'),
            t('meta.age', 'age') + '=' + String(cfg.age || 'auto'),
          ].join(' | ');
          rows.push(
            '<tr>' +
              '<td>' + escapeHtml(String(item.run_id || '-')) + '</td>' +
              '<td>' + escapeHtml(isoToLocal(item.started_at)) + '</td>' +
              '<td>' + escapeHtml(formatDuration(item.duration_sec)) + '</td>' +
              '<td><span class="result-pill ' + escapeHtml(state) + '">' + escapeHtml(localizeState(state)) + '</span></td>' +
              '<td>' + escapeHtml(String(item.success_books || 0) + '/' + String(item.total_books || 0)) + '</td>' +
              '<td>' + escapeHtml(cfgText) + '</td>' +
            '</tr>'
          );
        }
        body.innerHTML = rows.join('');
      }

      const selector = byId('detail_run_select');
      const oldValue = selector.value;
      const options = [];
      for (let i = 0; i < ui.historyRows.length; i += 1) {
        const item = ui.historyRows[i] || {};
        const runId = String(item.run_id || '');
        if (!runId) continue;
        const state = String(item.state || 'unknown');
        options.push('<option value="' + escapeHtml(runId) + '">' + escapeHtml(runId + ' (' + state + ')') + '</option>');
      }
      if (!options.length) {
        selector.innerHTML = '<option value="">' + escapeHtml(t('msg.no_runs_available', 'No runs available')) + '</option>';
        ui.selectedRunId = '';
      } else {
        selector.innerHTML = options.join('');
        if (oldValue && options.join('').indexOf('value="' + oldValue + '"') >= 0) {
          selector.value = oldValue;
        } else if (ui.selectedRunId && options.join('').indexOf('value="' + ui.selectedRunId + '"') >= 0) {
          selector.value = ui.selectedRunId;
        } else {
          selector.selectedIndex = 0;
          ui.selectedRunId = selector.value;
        }
      }

      updateEvaluationRunSelect();
    }

    function setEvaluationStatus(text, mode) {
      const box = byId('eval_status');
      if (!box) return;
      box.textContent = String(text || '');
      box.className = 'message subtle';
      if (mode) box.classList.add(mode);
    }

    function clearEvaluationChart() {
      if (ui.evaluation && ui.evaluation.chart) {
        try {
          ui.evaluation.chart.destroy();
        } catch (_err) {
        }
        ui.evaluation.chart = null;
      }
    }

    function formatBookOptionLabel(book, fallbackIndex) {
      const item = book && typeof book === 'object' ? book : {};
      const index = parseIntSafe(item.book_index, fallbackIndex || 0);
      const safeIndex = index > 0 ? index : (fallbackIndex || 1);
      const titleRaw = String(item.title || item.story_root || ('book_' + String(safeIndex))).trim();
      const title = titleRaw || ('book_' + String(safeIndex));
      const score = parseFloatSafe(item.overall_score, Number.NaN);
      let label = '#' + String(safeIndex) + ' ' + title;
      if (Number.isFinite(score)) {
        label += ' (' + score.toFixed(1) + ')';
      }
      return label;
    }

    function updateDetailBookSelect(data, runId) {
      const selector = byId('detail_book_select');
      if (!selector) return null;

      const books = Array.isArray(data && data.books) ? data.books : [];
      const selectedBook = data && data.selected_book && typeof data.selected_book === 'object'
        ? data.selected_book
        : null;

      const runToken = String(runId || '').trim();
      const mappedValue = runToken ? String(ui.selectedRunBookByRun[runToken] || '').trim() : '';
      const oldValue = String(selector.value || mappedValue || '').trim();

      if (!books.length) {
        selector.innerHTML = '<option value="">' + escapeHtml(t('msg.eval_no_books', 'No books found in this run.')) + '</option>';
        selector.value = '';
        return null;
      }

      const options = [];
      for (let i = 0; i < books.length; i += 1) {
        const book = books[i] || {};
        const bookId = String(book.book_id || ('book-' + String(i + 1))).trim();
        const label = formatBookOptionLabel(book, i + 1);
        options.push('<option value="' + escapeHtml(bookId) + '">' + escapeHtml(label) + '</option>');
      }
      selector.innerHTML = options.join('');

      let preferred = oldValue;
      if (!preferred && selectedBook) {
        preferred = String(selectedBook.book_id || '').trim();
      }
      if (!preferred && books.length) {
        preferred = String((books[books.length - 1] || {}).book_id || '').trim();
      }

      const escapedPreferred = 'value="' + preferred.replace(/"/g, '&quot;') + '"';
      if (preferred && selector.innerHTML.indexOf(escapedPreferred) >= 0) {
        selector.value = preferred;
      } else {
        selector.selectedIndex = Math.max(0, selector.options.length - 1);
      }

      const selectedValue = String(selector.value || '').trim();
      if (runToken && selectedValue) {
        ui.selectedRunBookByRun[runToken] = selectedValue;
      }

      for (let i = 0; i < books.length; i += 1) {
        const row = books[i] || {};
        if (String(row.book_id || '').trim() === selectedValue) {
          return row;
        }
      }
      return books[books.length - 1] || null;
    }

    function updateEvaluationBookSelect(books, selectedBook) {
      const selector = byId('eval_book_select');
      if (!selector) return null;

      const rows = Array.isArray(books) ? books : [];
      const selected = selectedBook && typeof selectedBook === 'object' ? selectedBook : null;
      const runToken = String(ui.evaluation.runId || '').trim();
      const mappedValue = runToken ? String(ui.selectedRunBookByRun[runToken] || '').trim() : '';
      const oldValue = String(selector.value || ui.evaluation.book || mappedValue || '').trim();

      if (!rows.length) {
        selector.innerHTML = '<option value="">' + escapeHtml(t('msg.eval_no_books', 'No books found in this run.')) + '</option>';
        ui.evaluation.book = '';
        return null;
      }

      const options = [];
      for (let i = 0; i < rows.length; i += 1) {
        const row = rows[i] || {};
        const bookId = String(row.book_id || ('book-' + String(i + 1))).trim();
        const label = formatBookOptionLabel(row, i + 1);
        options.push('<option value="' + escapeHtml(bookId) + '">' + escapeHtml(label) + '</option>');
      }
      selector.innerHTML = options.join('');

      let preferred = oldValue;
      if (!preferred && selected) {
        preferred = String(selected.book_id || '').trim();
      }
      if (!preferred && rows.length) {
        preferred = String((rows[rows.length - 1] || {}).book_id || '').trim();
      }

      const escapedPreferred = 'value="' + preferred.replace(/"/g, '&quot;') + '"';
      if (preferred && selector.innerHTML.indexOf(escapedPreferred) >= 0) {
        selector.value = preferred;
      } else {
        selector.selectedIndex = Math.max(0, selector.options.length - 1);
      }

      ui.evaluation.book = String(selector.value || '').trim();
      if (runToken && ui.evaluation.book) {
        ui.selectedRunBookByRun[runToken] = ui.evaluation.book;
      }

      for (let i = 0; i < rows.length; i += 1) {
        const row = rows[i] || {};
        if (String(row.book_id || '').trim() === ui.evaluation.book) {
          return row;
        }
      }
      return rows[rows.length - 1] || null;
    }

    function updateEvaluationRunSelect() {
      const selector = byId('eval_run_select');
      if (!selector) return;

      const previousRun = String(ui.evaluation.runId || '').trim();
      const oldValue = String(selector.value || ui.evaluation.runId || ui.selectedRunId || '').trim();
      const options = [];
      for (let i = 0; i < ui.historyRows.length; i += 1) {
        const item = ui.historyRows[i] || {};
        const runId = String(item.run_id || '').trim();
        if (!runId) continue;
        const state = String(item.state || 'unknown').toLowerCase();
        options.push('<option value="' + escapeHtml(runId) + '">' + escapeHtml(runId + ' (' + localizeState(state) + ')') + '</option>');
      }

      if (!options.length) {
        selector.innerHTML = '<option value="">' + escapeHtml(t('msg.no_runs_available', 'No runs available')) + '</option>';
        ui.evaluation.runId = '';
        updateEvaluationBookSelect([], null);
        return;
      }

      selector.innerHTML = options.join('');
      if (oldValue && options.join('').indexOf('value="' + oldValue + '"') >= 0) {
        selector.value = oldValue;
      } else if (ui.selectedRunId && options.join('').indexOf('value="' + ui.selectedRunId + '"') >= 0) {
        selector.value = ui.selectedRunId;
      } else {
        selector.selectedIndex = 0;
      }
      ui.evaluation.runId = String(selector.value || '').trim();
      if (ui.evaluation.runId !== previousRun) {
        ui.evaluation.book = String(ui.selectedRunBookByRun[ui.evaluation.runId] || '').trim();
      }
    }

    function syncEvaluationSourceControls() {
      const sourceNode = byId('evaluation_source');
      const runGroup = byId('eval_source_run_group');
      const bookGroup = byId('eval_source_book_group');
      const storyGroup = byId('eval_source_story_group');
      if (!sourceNode) return;

      const source = String(sourceNode.value || 'latest').trim();
      ui.evaluation.source = source;

      if (runGroup) {
        if (source === 'run') runGroup.classList.add('active');
        else runGroup.classList.remove('active');
      }
      if (bookGroup) {
        if (source === 'run') bookGroup.classList.add('active');
        else bookGroup.classList.remove('active');
      }
      if (storyGroup) {
        if (source === 'story_root') storyGroup.classList.add('active');
        else storyGroup.classList.remove('active');
      }

      if (source === 'run') {
        updateEvaluationRunSelect();
      } else {
        ui.evaluation.book = '';
        updateEvaluationBookSelect([], null);
      }
    }

    function renderEvaluation(data, options) {
      const opts = options && typeof options === 'object' ? options : {};
      const preserveStatus = !!opts.preserveStatus;
      const payload = data && typeof data === 'object' ? data : {};
      ui.evaluation.lastResponse = payload;

      const scoreNode = byId('eval_overall_score');
      const scopeNode = byId('eval_scope');
      const branchNode = byId('eval_branch_used');
      const reportNode = byId('eval_report_file');
      const sourceNode = byId('eval_source_used');
      const runNode = byId('eval_run_used');
      const bookNode = byId('eval_book_used');
      const storyRootNode = byId('eval_story_root_used');
      const logsNode = byId('eval_logs');

      const books = Array.isArray(payload.books) ? payload.books : [];
      const payloadSelectedBook = payload.selected_book && typeof payload.selected_book === 'object'
        ? payload.selected_book
        : null;

      if (!payload || payload.ok === false) {
        clearEvaluationChart();

        if (scoreNode) scoreNode.textContent = '-';
        if (scopeNode) scopeNode.textContent = '-';
        if (branchNode) branchNode.textContent = '-';
        if (reportNode) reportNode.textContent = '-';
        if (sourceNode) sourceNode.textContent = String((payload.meta && payload.meta.source) || ui.evaluation.source || '-');
        if (runNode) runNode.textContent = String((payload.meta && payload.meta.run_id) || ui.evaluation.runId || '-');
        if (bookNode) bookNode.textContent = '-';
        if (storyRootNode) storyRootNode.textContent = String((payload.meta && payload.meta.story_root) || ui.evaluation.storyRoot || '-');

        if (ui.evaluation.source === 'run') {
          updateEvaluationBookSelect(books, payloadSelectedBook);
        }

        if (logsNode) {
          const errorText = String(payload.error || t('msg.eval_no_data', 'No evaluation loaded.'));
          logsNode.textContent = errorText;
        }

        if (!preserveStatus) {
          setEvaluationStatus(String(payload.error || t('msg.eval_fetch_failed', 'Failed to load evaluation report.')), 'warn');
        }
        return;
      }

      const diagnostics = payload.diagnostics && typeof payload.diagnostics === 'object' ? payload.diagnostics : {};
      const meta = payload.meta && typeof payload.meta === 'object' ? payload.meta : {};
      const overall = parseFloatSafe(diagnostics.overall_score, Number.NaN);
      const scope = String(diagnostics.evaluation_scope || '-');
      const branchUsed = String(diagnostics.branch_id || payload.requested_branch || meta.requested_branch || ui.evaluation.branch || '-');
      const reportFile = String(payload.report_file || meta.report_file || '-');
      const sourceUsed = String(payload.source || meta.source || ui.evaluation.source || '-');
      const runUsed = String(payload.run_id || meta.run_id || '-');
      let selectedBook = null;
      if (sourceUsed === 'run' || ui.evaluation.source === 'run') {
        selectedBook = updateEvaluationBookSelect(books, payloadSelectedBook);
      } else {
        updateEvaluationBookSelect([], null);
      }
      const selectedBookLabel = selectedBook ? formatBookOptionLabel(selectedBook, parseIntSafe(selectedBook.book_index, 1)) : '-';
      const storyRootUsed = String(
        (selectedBook && selectedBook.story_root) || payload.story_root || meta.story_root || '-'
      );

      if (scoreNode) scoreNode.textContent = Number.isFinite(overall) ? overall.toFixed(1) : '-';
      if (scopeNode) scopeNode.textContent = scope;
      if (branchNode) branchNode.textContent = branchUsed;
      if (reportNode) reportNode.textContent = reportFile;
      if (sourceNode) sourceNode.textContent = sourceUsed;
      if (runNode) runNode.textContent = runUsed;
      if (bookNode) bookNode.textContent = selectedBookLabel;
      if (storyRootNode) storyRootNode.textContent = storyRootUsed;

      if (logsNode) {
        logsNode.textContent = JSON.stringify(diagnostics, null, 2);
      }

      const scoreMap = diagnostics.dimension_scores && typeof diagnostics.dimension_scores === 'object'
        ? diagnostics.dimension_scores
        : {};
      const dimensionOrder = ['readability', 'factuality', 'emotional_impact', 'completeness', 'entity_consistency', 'coherence'];
      const dimensions = [];
      for (let i = 0; i < dimensionOrder.length; i += 1) {
        const key = dimensionOrder[i];
        if (Object.prototype.hasOwnProperty.call(scoreMap, key)) {
          dimensions.push(key);
        }
      }
      const rawDimensionKeys = Object.keys(scoreMap);
      for (let i = 0; i < rawDimensionKeys.length; i += 1) {
        const key = rawDimensionKeys[i];
        if (dimensions.indexOf(key) === -1) {
          dimensions.push(key);
        }
      }

      const dimensionLabelsZh = {
        readability: '可讀性',
        factuality: '事實性',
        emotional_impact: '情感影響',
        completeness: '完整度',
        entity_consistency: '實體一致性',
        coherence: '連貫性',
      };
      const dimensionLabelsEn = {
        readability: 'Readability',
        factuality: 'Factuality',
        emotional_impact: 'Emotional Impact',
        completeness: 'Completeness',
        entity_consistency: 'Entity Consistency',
        coherence: 'Coherence',
      };
      const dimensionMap = ui.language === 'zh-TW' ? dimensionLabelsZh : dimensionLabelsEn;
      const chartLabels = [];
      const values = [];
      for (let i = 0; i < dimensions.length; i += 1) {
        const key = dimensions[i];
        values.push(parseFloatSafe(scoreMap[key], 0));
        chartLabels.push(dimensionMap[key] || key.replace(/_/g, ' '));
      }

      clearEvaluationChart();
      const chartCanvas = byId('evalRadarChart');
      if (chartCanvas && dimensions.length && window.Chart) {
        const ctx = chartCanvas.getContext('2d');
        const gradient = ctx
          ? (function () {
              const g = ctx.createLinearGradient(0, 0, 0, Math.max(chartCanvas.clientHeight || 320, 320));
              g.addColorStop(0, 'rgba(14, 165, 233, 0.34)');
              g.addColorStop(1, 'rgba(37, 99, 235, 0.08)');
              return g;
            })()
          : 'rgba(37, 99, 235, 0.16)';

        ui.evaluation.chart = new window.Chart(chartCanvas, {
          type: 'radar',
          data: {
            labels: chartLabels,
            datasets: [
              {
                label: t('eval.overall', 'Overall Score'),
                data: values,
                fill: true,
                backgroundColor: gradient,
                borderColor: '#1d4ed8',
                borderWidth: 2.6,
                pointBackgroundColor: '#0ea5e9',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointHoverBackgroundColor: '#0284c7',
                pointHoverBorderColor: '#ffffff',
              },
              {
                label: ui.language === 'zh-TW' ? '參考線 70' : 'Reference 70',
                data: values.map(function () { return 70; }),
                fill: false,
                borderColor: 'rgba(148, 163, 184, 0.85)',
                borderDash: [5, 4],
                borderWidth: 1.5,
                pointRadius: 0,
                pointHoverRadius: 0,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
              duration: 760,
              easing: 'easeOutQuart',
            },
            plugins: {
              legend: {
                display: true,
                labels: {
                  usePointStyle: true,
                  boxWidth: 10,
                  color: '#334155',
                  font: {
                    size: 12,
                    weight: '600',
                  },
                },
              },
              tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.94)',
                titleColor: '#f8fafc',
                bodyColor: '#e2e8f0',
                borderColor: '#1d4ed8',
                borderWidth: 1,
                padding: 10,
                callbacks: {
                  label: function (ctx) {
                    const value = parseFloatSafe(ctx.parsed.r, 0);
                    const label = String(ctx.dataset.label || '');
                    return label + ': ' + value.toFixed(1);
                  },
                },
              },
            },
            scales: {
              r: {
                beginAtZero: true,
                min: 0,
                max: 100,
                angleLines: {
                  color: 'rgba(148, 163, 184, 0.28)',
                },
                grid: {
                  color: 'rgba(148, 163, 184, 0.22)',
                },
                pointLabels: {
                  color: '#334155',
                  font: {
                    size: 12,
                    weight: '600',
                  },
                },
                ticks: {
                  stepSize: 20,
                  color: '#64748b',
                  backdropColor: 'rgba(255, 255, 255, 0.82)',
                },
              },
            },
          },
        });
      } else if (chartCanvas && dimensions.length === 0) {
        const ctx = chartCanvas.getContext('2d');
        if (ctx) {
          ctx.clearRect(0, 0, chartCanvas.width, chartCanvas.height);
          ctx.font = '14px sans-serif';
          ctx.fillStyle = '#6b7280';
          ctx.fillText(t('msg.eval_no_dimensions', 'No dimension score found in this report.'), 16, 28);
        }
      }

      if (!preserveStatus) {
        setEvaluationStatus('', '');
      }
    }

    async function fetchEvaluation(force) {
      if (!force && ui.activeTab !== 'evaluation') return null;

      const sourceControl = byId('evaluation_source');
      const runControl = byId('eval_run_select');
      const bookControl = byId('eval_book_select');
      const storyRootControl = byId('evaluation_story_root');
      const branchControl = byId('evaluation_branch');

      const source = sourceControl ? String(sourceControl.value || 'latest').trim() : 'latest';
      const runId = runControl ? String(runControl.value || '').trim() : '';
      const book = bookControl ? String(bookControl.value || '').trim() : '';
      const storyRoot = storyRootControl ? String(storyRootControl.value || '').trim() : '';
      const branch = branchControl ? String(branchControl.value || 'canonical').trim() : 'canonical';

      ui.evaluation.source = source || 'latest';
      ui.evaluation.runId = runId;
      ui.evaluation.book = ui.evaluation.source === 'run' ? book : '';
      ui.evaluation.storyRoot = storyRoot;
      ui.evaluation.branch = branch || 'canonical';

      if (ui.evaluation.source === 'run' && !ui.evaluation.runId) {
        setEvaluationStatus(t('msg.eval_run_required', 'Please select a run ID first.'), 'warn');
        return null;
      }
      if (ui.evaluation.source === 'story_root' && !ui.evaluation.storyRoot) {
        setEvaluationStatus(t('msg.eval_story_root_required', 'Please enter story_root first.'), 'warn');
        return null;
      }

      const params = new URLSearchParams();
      params.set('source', ui.evaluation.source);
      params.set('branch', ui.evaluation.branch || 'canonical');
      if (ui.evaluation.source === 'run') {
        params.set('run_id', ui.evaluation.runId);
        if (ui.evaluation.book) {
          params.set('book', ui.evaluation.book);
        }
      }
      if (ui.evaluation.source === 'story_root') {
        params.set('story_root', ui.evaluation.storyRoot);
      }

      setEvaluationStatus(t('msg.eval_loading', 'Loading evaluation report...'), 'ok');
      try {
        const data = await apiGet('/api/evaluation?' + params.toString());
        renderEvaluation(data);
        return data;
      } catch (err) {
        const message = String((err && err.message) || err || t('msg.eval_fetch_failed', 'Failed to load evaluation report.'));
        setEvaluationStatus(message, 'bad');
        renderEvaluation({ok: false, error: message});
        return null;
      }
    }

    function renderQueue(data) {
      const body = byId('queue_body');
      const active = data.active_job;
      const pending = Array.isArray(data.pending_jobs) ? data.pending_jobs : [];
      const rows = [];

      if (active) {
        rows.push(
          '<tr>' +
            '<td>' + escapeHtml(String(active.job_id || '-')) + '</td>' +
            '<td><span class="result-pill running">' + escapeHtml(localizeState('active')) + '</span></td>' +
            '<td>' + escapeHtml(t('module.priority.' + String(active.priority || 'normal'), String(active.priority || 'normal'))) + '</td>' +
            '<td>' + escapeHtml(String(active.count || 0)) + '</td>' +
            '<td>' + escapeHtml(String(active.category || 'auto')) + '</td>' +
            '<td>' + escapeHtml(String(active.age || 'auto')) + '</td>' +
            '<td>-</td>' +
          '</tr>'
        );
      }

      for (let i = 0; i < pending.length; i += 1) {
        const item = pending[i] || {};
        const jobId = String(item.job_id || '');
        rows.push(
          '<tr>' +
            '<td>' + escapeHtml(jobId) + '</td>' +
            '<td><span class="result-pill">' + escapeHtml(localizeState('queued')) + '</span></td>' +
            '<td>' +
              '<select data-job-priority="' + escapeHtml(jobId) + '">' +
                '<option value="high"' + (item.priority === 'high' ? ' selected' : '') + '>' + escapeHtml(t('module.priority.high', 'high')) + '</option>' +
                '<option value="normal"' + (item.priority === 'normal' ? ' selected' : '') + '>' + escapeHtml(t('module.priority.normal', 'normal')) + '</option>' +
                '<option value="low"' + (item.priority === 'low' ? ' selected' : '') + '>' + escapeHtml(t('module.priority.low', 'low')) + '</option>' +
              '</select>' +
            '</td>' +
            '<td>' + escapeHtml(String(item.count || 0)) + '</td>' +
            '<td>' + escapeHtml(String(item.category || 'auto')) + '</td>' +
            '<td>' + escapeHtml(String(item.age || 'auto')) + '</td>' +
            '<td>' +
              '<button class="btn ghost mini" data-action="reprioritize" data-job-id="' + escapeHtml(jobId) + '">' + escapeHtml(t('btn.apply', 'Apply')) + '</button> ' +
              '<button class="btn danger mini" data-action="cancel" data-job-id="' + escapeHtml(jobId) + '">' + escapeHtml(t('btn.cancel', 'Cancel')) + '</button>' +
            '</td>' +
          '</tr>'
        );
      }

      if (!rows.length) {
        body.innerHTML = '<tr><td colspan="7">' + escapeHtml(t('msg.queue_empty', 'Queue is empty.')) + '</td></tr>';
      } else {
        body.innerHTML = rows.join('');
      }
    }

    function renderAlerts(items) {
      const list = byId('alert_list');
      if (!Array.isArray(items) || !items.length) {
        list.innerHTML = '<div class="list-item">' + escapeHtml(t('msg.no_alerts', 'No alerts.')) + '</div>';
        return;
      }
      const rows = [];
      for (let i = 0; i < items.length; i += 1) {
        const item = items[i] || {};
        const level = String(item.level || 'info').toLowerCase();
        rows.push(
          '<div class="list-item level-' + escapeHtml(level) + '">' +
            '<b>' + escapeHtml(String(item.title || t('ops.alert.title', 'Alert Center'))) + '</b>' +
            '<div>' + escapeHtml(String(item.message || '')) + '</div>' +
            '<div class="meta">' + escapeHtml(isoToLocal(item.ts)) + (item.run_id ? ' | run=' + escapeHtml(String(item.run_id)) : '') + '</div>' +
            (item.acknowledged ? '' : '<div style="margin-top:6px"><button class="btn ghost mini" data-action="ack-alert" data-alert-id="' + escapeHtml(String(item.alert_id || '')) + '">' + escapeHtml(t('btn.acknowledge', 'Acknowledge')) + '</button></div>') +
          '</div>'
        );
      }
      list.innerHTML = rows.join('');
    }

    function renderCapacity(data) {
      byId('cap_runs').textContent = String(data.window_runs || 0);
      byId('cap_success_rate').textContent = toPercent(data.success_rate_pct || 0);
      byId('cap_throughput').textContent = String(parseFloatSafe(data.books_per_hour, 0).toFixed(2));
      byId('cap_queue_delay').textContent = formatDuration(data.avg_queue_delay_sec || 0);
      byId('cap_gpu_hours').textContent = String(parseFloatSafe(data.gpu_hours, 0).toFixed(2));
      byId('cap_gpu_cost').textContent = '$' + parseFloatSafe(data.gpu_cost_usd, 0).toFixed(2);

      const trend = byId('capacity_trend');
      const rows = Array.isArray(data.trend) ? data.trend : [];
      if (!rows.length) {
        trend.innerHTML = '<div class="list-item">' + escapeHtml(t('msg.no_trend_data', 'No trend data yet.')) + '</div>';
      } else {
        const html = [];
        for (let i = 0; i < rows.length; i += 1) {
          const row = rows[i] || {};
          html.push(
            '<div class="list-item">' +
              '<b>' + escapeHtml(String(row.run_id || '-')) + '</b>' +
              '<div class="meta">' +
                escapeHtml(String(row.state || '-')) +
                ' | duration=' + escapeHtml(formatDuration(row.duration_sec || 0)) +
                ' | success=' + escapeHtml(String(row.success_books || 0) + '/' + String(row.total_books || 0)) +
              '</div>' +
            '</div>'
          );
        }
        trend.innerHTML = html.join('');
      }
    }

    function renderConfigVersions(items) {
      const body = byId('config_versions_body');
      if (!Array.isArray(items) || !items.length) {
        body.innerHTML = '<tr><td colspan="5">' + escapeHtml(t('msg.no_saved_versions', 'No saved versions.')) + '</td></tr>';
        return;
      }

      const rows = [];
      for (let i = 0; i < items.length; i += 1) {
        const item = items[i] || {};
        const id = String(item.version_id || '');
        rows.push(
          '<tr>' +
            '<td>' + escapeHtml(String(item.name || id)) + '</td>' +
            '<td>' + escapeHtml(isoToLocal(item.created_at)) + '</td>' +
            '<td>' + escapeHtml(String(item.note || '')) + '</td>' +
            '<td>' + escapeHtml(String(item.usage_count || 0)) + '</td>' +
            '<td><button class="btn ghost mini" data-action="apply-config" data-version-id="' + escapeHtml(id) + '">' + escapeHtml(t('btn.apply', 'Apply')) + '</button></td>' +
          '</tr>'
        );
      }
      body.innerHTML = rows.join('');
    }

    function renderRunDetail(data) {
      const run = data.run || {};
      const runId = String(run.run_id || ui.selectedRunId || '').trim();
      const selectedBook = updateDetailBookSelect(data, runId);

      byId('detail_state').textContent = localizeState(run.state || '-');
      byId('detail_duration').textContent = formatDuration(run.duration_sec);
      byId('detail_exit').textContent = run.exit_code == null ? '-' : String(run.exit_code);
      byId('detail_books_total').textContent = String(run.total_books || 0);
      byId('detail_books_success').textContent = String(run.success_books || 0);
      byId('detail_books_fail').textContent = String(run.failed_books || 0);
      byId('detail_priority').textContent = String(run.priority || '-');
      byId('detail_queue_delay').textContent = formatDuration(run.queued_delay_sec || 0);
      byId('detail_started').textContent = isoToLocal(run.started_at);
      byId('detail_finished').textContent = isoToLocal(run.finished_at);
      byId('detail_json').textContent = JSON.stringify(data, null, 2);

      if (ui.evaluation.source === 'run' && ui.evaluation.runId === runId && selectedBook) {
        ui.evaluation.book = String(selectedBook.book_id || '').trim();
        const evalBookSelect = byId('eval_book_select');
        if (evalBookSelect && evalBookSelect.value !== ui.evaluation.book) {
          evalBookSelect.value = ui.evaluation.book;
        }
      }

      const eventBox = byId('detail_events');
      const events = Array.isArray(data.events) ? data.events : [];
      if (!events.length) {
        eventBox.innerHTML = '<div class="event-item">' + escapeHtml(t('msg.no_events', 'No events.')) + '</div>';
      } else {
        const html = [];
        for (let i = 0; i < events.length; i += 1) {
          const ev = events[i] || {};
          const details = ev.details || {};
          html.push(
            '<div class="event-item">' +
              '<b>' + escapeHtml(String(ev.event || '-')) + '</b>' +
              '<div class="meta">' + escapeHtml(isoToLocal(ev.ts)) + '</div>' +
              '<div class="meta">' + escapeHtml(JSON.stringify(details)) + '</div>' +
            '</div>'
          );
        }
        eventBox.innerHTML = html.join('');
      }

      const detailAlerts = byId('detail_alerts');
      const alerts = Array.isArray(data.alerts) ? data.alerts : [];
      if (!alerts.length) {
        detailAlerts.innerHTML = '<div class="list-item">' + escapeHtml(t('msg.no_related_alerts', 'No related alerts.')) + '</div>';
      } else {
        const html = [];
        for (let i = 0; i < alerts.length; i += 1) {
          const item = alerts[i] || {};
          html.push(
            '<div class="list-item">' +
              '<b>' + escapeHtml(String(item.title || t('ops.alert.title', 'Alert Center'))) + '</b>' +
              '<div>' + escapeHtml(String(item.message || '')) + '</div>' +
              '<div class="meta">' + escapeHtml(isoToLocal(item.ts)) + '</div>' +
              (item.acknowledged ? '' : '<div style="margin-top:6px"><button class="btn ghost mini" data-action="ack-alert" data-alert-id="' + escapeHtml(String(item.alert_id || '')) + '">' + escapeHtml(t('btn.acknowledge', 'Acknowledge')) + '</button></div>') +
            '</div>'
          );
        }
        detailAlerts.innerHTML = html.join('');
      }

      const logs = Array.isArray(data.logs) ? data.logs : [];
      let blob = '';
      for (let i = 0; i < logs.length; i += 1) {
        const line = logs[i] || {};
        const ts = line.ts ? String(line.ts).slice(11, 19) : '--:--:--';
        blob += '[' + ts + '] ' + String(line.text || '') + '\n';
      }
      byId('detail_logs').textContent = blob || t('msg.no_run_logs', 'No run logs.');
    }

    function clearRunDetailPanel() {
      byId('detail_state').textContent = '-';
      byId('detail_duration').textContent = '-';
      byId('detail_exit').textContent = '-';
      byId('detail_books_total').textContent = '-';
      byId('detail_books_success').textContent = '-';
      byId('detail_books_fail').textContent = '-';
      byId('detail_priority').textContent = '-';
      byId('detail_queue_delay').textContent = '-';
      byId('detail_started').textContent = '-';
      byId('detail_finished').textContent = '-';
      byId('detail_json').textContent = '{}';
      byId('detail_events').innerHTML = '<div class="event-item">' + escapeHtml(t('msg.no_events', 'No events.')) + '</div>';
      byId('detail_alerts').innerHTML = '<div class="list-item">' + escapeHtml(t('msg.no_related_alerts', 'No related alerts.')) + '</div>';
      byId('detail_logs').textContent = t('msg.no_run_logs', 'No run logs.');

      const bookSelector = byId('detail_book_select');
      if (bookSelector) {
        bookSelector.innerHTML = '<option value="">' + escapeHtml(t('eval.book.latest', 'Latest book')) + '</option>';
        bookSelector.value = '';
      }
    }

    async function fetchStatus() {
      const data = await apiGet('/api/status');
      renderStatus(data);
      return data;
    }

    async function fetchLogs() {
      if (!ui.activeLogRunId) return null;
      const path = '/api/logs?since=' + String(ui.logCursor) + '&limit=500&run_id=' + encodeURIComponent(ui.activeLogRunId);
      const data = await apiGet(path);
      appendLogs(data.lines || []);
      if (Number.isFinite(Number(data.next_seq))) {
        ui.logCursor = Number(data.next_seq);
      }
      return data;
    }

    async function fetchHistory() {
      const data = await apiGet('/api/history?limit=20');
      renderHistory(data.items || []);
      return data;
    }

    async function fetchQueue() {
      const data = await apiGet('/api/queue');
      renderQueue(data);
      return data;
    }

    async function fetchAlerts() {
      const data = await apiGet('/api/alerts?limit=30');
      renderAlerts(data.items || []);
      return data;
    }

    async function fetchCapacity() {
      const data = await apiGet('/api/capacity?window=' + String("" + 40));
      renderCapacity(data);
      return data;
    }

    async function fetchConfigVersions() {
      const data = await apiGet('/api/configs?limit=20');
      renderConfigVersions(data.items || []);
      return data;
    }

    async function fetchRunDetail() {
      const runId = byId('detail_run_select').value;
      ui.selectedRunId = runId;
      if (!runId) {
        clearRunDetailPanel();
        return null;
      }
      const selectedBook = String(ui.selectedRunBookByRun[runId] || '').trim();
      let path = '/api/run-detail?run_id=' + encodeURIComponent(runId) + '&log_limit=1200&event_limit=260';
      if (selectedBook) {
        path += '&book=' + encodeURIComponent(selectedBook);
      }
      const data = await apiGet(path);
      renderRunDetail(data);
      return data;
    }

    async function startRun() {
      const payload = payloadFromForm();
      if (payload.count < 1) {
        setMessage(t('msg.book_count_min', 'Book count must be >= 1.'), 'bad');
        return;
      }
      setMessage(t('msg.submitting_run_request', 'Submitting run request...'), 'ok');

      try {
        const data = await apiPost('/api/start', payload);
        saveLocalForm();

        if (data.started) {
          setMessage(tf('msg.run_started', {id: String(data.run_id || '')}, 'Run started: {id}'), 'ok');
          const opsLogs = byId('log_output');
          if (opsLogs) opsLogs.textContent = '';
          const overviewLogs = byId('overview_log_output');
          if (overviewLogs) overviewLogs.textContent = '';
          ui.activeLogRunId = data.run_id || null;
          ui.logCursor = Number(data.log_next_seq || 0);
        } else {
          setMessage(tf('msg.run_queued', {pos: String(data.queue_position || '?')}, 'Run queued at position {pos}.'), 'warn');
        }
        await refreshOverview(true);
      } catch (err) {
        setMessage(String((err && err.message) || err || t('msg.failed_start_run', 'Failed to start run.')), 'bad');
      }
    }

    async function stopRun() {
      setMessage(t('msg.stopping_active_run', 'Stopping active run...'), 'warn');
      try {
        const data = await apiPost('/api/stop', {});
        const msg = data.started_next
          ? t('msg.stopped_and_started_next', 'Stopped current run and started next queued run.')
          : String(data.message || t('msg.stopped', 'Stopped.'));
        setMessage(msg, 'warn');
        await refreshOverview(true);
      } catch (err) {
        setMessage(String((err && err.message) || err || t('msg.failed_stop_run', 'Failed to stop run.')), 'bad');
      }
    }

    async function clearOverviewView() {
      const status = ui.latestStatus || {};
      const running = Boolean(status.running);
      const queueDepth = parseIntSafe(status.queue_depth, 0);
      if (running || queueDepth > 0) {
        setMessage(t('msg.clear_history_blocked_running', 'Stop active and queued runs before clearing history.'), 'warn');
        return;
      }

      const confirmed = window.confirm(t('confirm.clear_overview_view', 'Clear live overview panel data only? Operations history will be kept.'));
      if (!confirmed) return;

      setMessage(t('msg.clearing_overview_view', 'Clearing overview panel...'), 'warn');
      try {
        const data = await apiPost('/api/overview/clear', {});
        const removed = parseIntSafe(data.removed_live_lines, 0);
        setMessage(tf('msg.cleared_overview_view', {count: String(removed)}, 'Overview panel cleared ({count} live lines).'), 'ok');

        ui.activeLogRunId = null;
        ui.logCursor = 0;
        const overviewLogOutput = byId('overview_log_output');
        if (overviewLogOutput) {
          overviewLogOutput.textContent = t('msg.no_live_logs', 'No active run logs yet.');
        }

        await refreshOverview(true);
      } catch (err) {
        setMessage(String((err && err.message) || err || t('msg.failed_clear_overview_view', 'Failed to clear overview panel.')), 'bad');
      }
    }

    async function clearRunHistory() {
      const status = ui.latestStatus || {};
      const running = Boolean(status.running);
      const queueDepth = parseIntSafe(status.queue_depth, 0);
      if (running || queueDepth > 0) {
        setMessage(t('msg.clear_history_blocked_running', 'Stop active and queued runs before clearing history.'), 'warn');
        return;
      }

      const confirmed = window.confirm(t('confirm.clear_run_history', 'Clear all run history records and related logs?'));
      if (!confirmed) return;

      setMessage(t('msg.clearing_run_history', 'Clearing run history...'), 'warn');
      try {
        const data = await apiPost('/api/history/clear', {});
        const removed = parseIntSafe(data.removed_runs, 0);
        setMessage(tf('msg.cleared_run_history', {count: String(removed)}, 'Run history cleared ({count} items).'), 'ok');

        ui.historyRows = [];
        ui.selectedRunId = '';
        ui.activeLogRunId = null;
        ui.logCursor = 0;

        const opsLogs = byId('log_output');
        if (opsLogs) opsLogs.textContent = '';
        const overviewLogOutput = byId('overview_log_output');
        if (overviewLogOutput) {
          overviewLogOutput.textContent = t('msg.no_live_logs', 'No active run logs yet.');
        }

        renderHistory([]);
        clearRunDetailPanel();
        await refreshOverview(true);
      } catch (err) {
        setMessage(String((err && err.message) || err || t('msg.failed_clear_run_history', 'Failed to clear run history.')), 'bad');
      }
    }

    async function saveConfigVersion() {
      const payload = payloadFromForm();
      const name = byId('version_name').value.trim();
      const note = byId('version_note').value.trim();
      try {
        const data = await apiPost('/api/configs/save', {
          name: name || null,
          note: note || null,
          payload: payload,
        });
        setMessage(tf('msg.saved_config_version', {id: String((data.version || {}).version_id || '')}, 'Saved config version: {id}'), 'ok');
        byId('version_name').value = '';
        byId('version_note').value = '';
        await fetchConfigVersions();
      } catch (err) {
        setMessage(String((err && err.message) || err || t('msg.failed_save_config_version', 'Failed to save config version.')), 'bad');
      }
    }

    async function applyConfigVersion(versionId) {
      try {
        const data = await apiPost('/api/configs/apply', {version_id: versionId});
        setFormFromPayload(data.config || {});
        setMessage(tf('msg.applied_config_version', {id: String(versionId)}, 'Applied config version: {id}'), 'ok');
      } catch (err) {
        setMessage(String((err && err.message) || err || t('msg.failed_apply_config_version', 'Failed to apply config version.')), 'bad');
      }
    }

    async function reprioritizeJob(jobId) {
      const selector = document.querySelector('[data-job-priority="' + jobId + '"]');
      if (!selector) return;
      const priority = selector.value || 'normal';
      try {
        await apiPost('/api/queue/reprioritize', {job_id: jobId, priority: priority});
        setMessage(tf('msg.updated_priority', {id: String(jobId)}, 'Updated priority for job {id}.'), 'ok');
        await fetchQueue();
      } catch (err) {
        setMessage(String((err && err.message) || err || t('msg.failed_reprioritize_job', 'Failed to reprioritize job.')), 'bad');
      }
    }

    async function cancelJob(jobId) {
      try {
        await apiPost('/api/queue/cancel', {job_id: jobId});
        setMessage(tf('msg.canceled_job', {id: String(jobId)}, 'Canceled queued job {id}.'), 'warn');
        await fetchQueue();
      } catch (err) {
        setMessage(String((err && err.message) || err || t('msg.failed_cancel_job', 'Failed to cancel job.')), 'bad');
      }
    }

    async function acknowledgeAlert(alertId) {
      try {
        await apiPost('/api/alerts/ack', {alert_id: alertId});
        await fetchAlerts();
        if (ui.activeTab === 'detail') {
          await fetchRunDetail();
        }
      } catch (err) {
        setMessage(String((err && err.message) || err || t('msg.failed_ack_alert', 'Failed to acknowledge alert.')), 'bad');
      }
    }

    async function refreshOverview(forceAll) {
      try {
        ui.refreshTick += 1;
        const status = await fetchStatus();
        const logsPromise = fetchLogs();
        const queuePromise = fetchQueue();
        const alertsPromise = fetchAlerts();
        const capacityPromise = fetchCapacity();
        const historyPromise = fetchHistory();
        const imagesPromise = (forceAll || ui.refreshTick % 3 === 0 || ui.activeTab === 'modules') ? fetchImages() : Promise.resolve(null);
        const configsPromise = (forceAll || ui.refreshTick % 3 === 0) ? fetchConfigVersions() : Promise.resolve(null);
        const modulesPromise = (forceAll || ui.refreshTick % 2 === 0 || ui.activeTab === 'modules') ? fetchModuleJobs() : Promise.resolve(null);
        const galleryPromise = (forceAll || ui.activeTab === 'gallery') ? fetchGallery(true) : Promise.resolve(null);
        const systemPromise = (forceAll || (ui.activeTab === 'gallery' && ui.refreshTick % 3 === 0)) ? pollSystemStatus(true) : Promise.resolve(null);
        const evaluationPromise = ui.activeTab === 'evaluation' ? fetchEvaluation(false) : Promise.resolve(null);

        const results = await Promise.all([
          logsPromise,
          queuePromise,
          alertsPromise,
          capacityPromise,
          historyPromise,
          imagesPromise,
          configsPromise,
          modulesPromise,
          galleryPromise,
          systemPromise,
          evaluationPromise,
        ]);

        const capacityData = results[3] || {};
        updateHeaderKpis(status, capacityData);
        setBackgroundMessage('', '');

        if (ui.activeTab === 'detail') {
          await fetchRunDetail();
        }
        if (ui.activeTab === 'modules' && ui.moduleSelectedJobId) {
          await fetchModuleJobDetail(ui.moduleSelectedJobId);
        }
      } catch (err) {
        setBackgroundMessage(String((err && err.message) || err || t('msg.refresh_failed', 'Refresh failed.')), 'warn');
      }
    }

    function switchTab(tabName) {
      ui.activeTab = tabName;
      const tabs = document.querySelectorAll('.tab-btn[data-tab]');
      for (let i = 0; i < tabs.length; i += 1) {
        const btn = tabs[i];
        if (btn.getAttribute('data-tab') === tabName) btn.classList.add('active');
        else btn.classList.remove('active');
      }
      const panels = [
        {name: 'gallery', id: 'tab_gallery'},
        {name: 'overview', id: 'tab_overview'},
        {name: 'ops', id: 'tab_ops'},
        {name: 'detail', id: 'tab_detail'},
        {name: 'evaluation', id: 'tab_evaluation'},
        {name: 'modules', id: 'tab_modules'},
      ];
      for (let i = 0; i < panels.length; i += 1) {
        const panel = byId(panels[i].id);
        if (!panel) continue;
        if (panels[i].name === tabName) panel.classList.add('active');
        else panel.classList.remove('active');
      }
      if (tabName === 'detail') {
        fetchRunDetail();
      }
      if (tabName === 'modules') {
        fetchModuleJobs();
        fetchTranslatableStories();
        if (ui.moduleSelectedJobId) {
          fetchModuleJobDetail(ui.moduleSelectedJobId);
        }
      }
      if (tabName === 'gallery') {
        fetchGallery(true);
        pollSystemStatus(true);
      }
      if (tabName === 'evaluation') {
        syncEvaluationSourceControls();
        fetchEvaluation(true);
      }
    }

    function restartTimer() {
      if (ui.timer) {
        clearInterval(ui.timer);
        ui.timer = null;
      }
      if (!byId('auto_refresh').checked) return;
      const ms = Math.max(1000, parseIntSafe(byId('refresh_ms').value, 2000));
      ui.timer = setInterval(function () {
        refreshOverview(false);
      }, ms);
    }

    function bindEvents() {
      byId('btn_start').addEventListener('click', startRun);
      byId('btn_stop').addEventListener('click', stopRun);
      byId('btn_save_template').addEventListener('click', saveTemplate);
      byId('btn_save_local').addEventListener('click', saveLocalForm);
      byId('btn_load_local').addEventListener('click', function () {
        loadLocalForm();
        setMessage(t('msg.loaded_local_profile', 'Loaded local profile.'), 'ok');
      });
      byId('btn_save_version').addEventListener('click', saveConfigVersion);
      byId('btn_refresh_now').addEventListener('click', function () {
        refreshOverview(true);
      });
      const overviewClearBtn = byId('btn_overview_clear_view');
      if (overviewClearBtn) {
        overviewClearBtn.addEventListener('click', clearOverviewView);
      }
      const clearHistoryBtn = byId('btn_clear_history');
      if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', clearRunHistory);
      }
      const clearLogsBtn = byId('btn_clear_logs');
      if (clearLogsBtn) {
        clearLogsBtn.addEventListener('click', function () {
          const opsLogs = byId('log_output');
          if (opsLogs) opsLogs.textContent = '';
          const overviewLogOutput = byId('overview_log_output');
          if (overviewLogOutput) {
            overviewLogOutput.textContent = t('msg.no_live_logs', 'No active run logs yet.');
          }
        });
      }
      byId('btn_detail_refresh').addEventListener('click', function () {
        fetchRunDetail();
      });
      byId('btn_images_refresh').addEventListener('click', function () {
        fetchImages();
      });
      byId('btn_images_regen').addEventListener('click', regenerateSelectedImages);
      byId('btn_images_module_run').addEventListener('click', runImageModuleJob);
      byId('btn_image_regen_detail').addEventListener('click', regenerateDetailImage);
      byId('btn_gallery_refresh').addEventListener('click', function () {
        fetchGallery(true);
        pollSystemStatus(true);
      });

      const evalRefreshBtn = byId('btn_eval_refresh');
      if (evalRefreshBtn) {
        evalRefreshBtn.addEventListener('click', function () {
          fetchEvaluation(true);
        });
      }
      const evalSource = byId('evaluation_source');
      if (evalSource) {
        evalSource.addEventListener('change', function () {
          syncEvaluationSourceControls();
          if (ui.activeTab === 'evaluation') fetchEvaluation(true);
        });
      }
      const evalRunSelect = byId('eval_run_select');
      if (evalRunSelect) {
        evalRunSelect.addEventListener('change', function () {
          ui.evaluation.runId = String(evalRunSelect.value || '').trim();
          ui.evaluation.book = String(ui.selectedRunBookByRun[ui.evaluation.runId] || '').trim();
          if (ui.activeTab === 'evaluation' && ui.evaluation.source === 'run') {
            fetchEvaluation(true);
          }
        });
      }
      const evalBookSelect = byId('eval_book_select');
      if (evalBookSelect) {
        evalBookSelect.addEventListener('change', function () {
          ui.evaluation.book = String(evalBookSelect.value || '').trim();
          if (ui.evaluation.source === 'run' && ui.evaluation.runId) {
            ui.selectedRunBookByRun[ui.evaluation.runId] = ui.evaluation.book;
          }
          if (ui.activeTab === 'evaluation' && ui.evaluation.source === 'run') {
            fetchEvaluation(true);
          }
        });
      }
      const evalStoryRoot = byId('evaluation_story_root');
      if (evalStoryRoot) {
        evalStoryRoot.addEventListener('change', function () {
          ui.evaluation.storyRoot = String(evalStoryRoot.value || '').trim();
          if (ui.activeTab === 'evaluation' && ui.evaluation.source === 'story_root') {
            fetchEvaluation(true);
          }
        });
      }
      const evalBranch = byId('evaluation_branch');
      if (evalBranch) {
        evalBranch.addEventListener('change', function () {
          ui.evaluation.branch = String(evalBranch.value || 'canonical').trim() || 'canonical';
          if (ui.activeTab === 'evaluation') {
            fetchEvaluation(true);
          }
        });
      }

      byId('btn_modules_refresh').addEventListener('click', function () {
        fetchModuleJobs();
        if (ui.moduleSelectedJobId) fetchModuleJobDetail(ui.moduleSelectedJobId, {log_limit: 400, event_limit: 260});
      });
      const moduleClearBtn = byId('btn_module_clear_view');
      if (moduleClearBtn) {
        moduleClearBtn.addEventListener('click', function () {
          clearModuleView();
        });
      }
      const moduleShowAllBtn = byId('btn_module_show_all');
      if (moduleShowAllBtn) {
        moduleShowAllBtn.addEventListener('click', function () {
          showAllModuleView();
        });
      }
      byId('btn_module_job_stop').addEventListener('click', function () {
        stopModuleJob(ui.moduleSelectedJobId);
      });

      byId('btn_module_story_run').addEventListener('click', runStoryModuleJob);
      byId('btn_module_translation_run').addEventListener('click', runTranslationModuleJob);
      byId('btn_module_voice_run').addEventListener('click', runVoiceModuleJob);
      byId('btn_module_trans_story_refresh').addEventListener('click', function () {
        fetchTranslatableStories();
      });
      byId('module_trans_story_select').addEventListener('change', applySelectedTranslationStory);
      byId('module_trans_source_folder').addEventListener('change', syncTranslationSourceLangByFolder);
      byId('btn_module_record_start').addEventListener('click', startModuleRecording);
      byId('btn_module_record_stop').addEventListener('click', stopModuleRecording);
      byId('btn_module_record_save').addEventListener('click', saveModuleRecordingAsSpeaker);
      byId('btn_general_text_run').addEventListener('click', runGeneralTextTool);
      byId('btn_general_image_run').addEventListener('click', runGeneralImageTool);
      byId('btn_general_translation_run').addEventListener('click', runGeneralTranslationTool);
      byId('btn_general_voice_run').addEventListener('click', runGeneralVoiceTool);
      byId('module_story_input_mode').addEventListener('change', syncModuleStoryInputMode);
      byId('story_input_mode').addEventListener('change', syncStoryInputMode);
      byId('btn_record_start').addEventListener('click', startRecording);
      byId('btn_record_stop').addEventListener('click', stopRecording);
      byId('btn_record_save').addEventListener('click', saveRecordingAsSpeaker);

      byId('auto_refresh').addEventListener('change', restartTimer);
      byId('refresh_ms').addEventListener('change', restartTimer);
      byId('lang_select').addEventListener('change', function () {
        const value = String(byId('lang_select').value || 'en');
        ui.language = value === 'zh-TW' ? 'zh-TW' : 'en';
        localStorage.setItem(LANG_STORE_KEY, ui.language);
        applyLanguage();
        syncStoryInputMode();
        syncModuleStoryInputMode();
        refreshOverview(true);
      });
      byId('detail_run_select').addEventListener('change', function () {
        const runId = String(byId('detail_run_select').value || '').trim();
        ui.selectedRunId = runId;
        if (ui.evaluation.source === 'run') {
          ui.evaluation.runId = ui.selectedRunId;
          ui.evaluation.book = String(ui.selectedRunBookByRun[ui.selectedRunId] || '').trim();
          updateEvaluationRunSelect();
        }
        fetchRunDetail();
      });

      const detailBookSelect = byId('detail_book_select');
      if (detailBookSelect) {
        detailBookSelect.addEventListener('change', function () {
          const runId = String(byId('detail_run_select').value || '').trim();
          const bookId = String(detailBookSelect.value || '').trim();
          if (runId) {
            ui.selectedRunBookByRun[runId] = bookId;
          }

          if (ui.evaluation.source === 'run' && ui.evaluation.runId === runId) {
            ui.evaluation.book = bookId;
            const evalBookNode = byId('eval_book_select');
            if (evalBookNode && evalBookNode.value !== bookId) {
              evalBookNode.value = bookId;
            }
            if (ui.activeTab === 'evaluation') {
              fetchEvaluation(true);
            }
          }
          fetchRunDetail();
        });
      }

      byId('template_select').addEventListener('change', function (event) {
        const target = event.target;
        if (!(target instanceof HTMLSelectElement)) return;
        const nameInput = byId('template_name_input');
        if (!target.value) {
          target.removeAttribute('data-selected-name');
          if (nameInput) nameInput.value = '';
          return;
        }

        const selected = target.options[target.selectedIndex] || null;
        const prompt = selected
          ? String(selected.getAttribute('data-prompt') || target.value || '')
          : String(target.value || '');
        const materials = selected
          ? String(selected.getAttribute('data-materials') || '')
          : '';
        const name = selected
          ? String(selected.getAttribute('data-name') || '')
          : '';

        byId('story_prompt').value = prompt;
        if (materials) {
          byId('story_materials').value = materials;
        }
        if (name) {
          target.setAttribute('data-selected-name', name);
          if (nameInput) nameInput.value = name;
        }
        setMessage(t('msg.template_loaded', 'Template loaded.'), 'ok');
      });

      const presetButtons = [
        {selector: '[data-preset="balanced"]', name: 'balanced'},
        {selector: '[data-preset="speed"]', name: 'speed'},
        {selector: '[data-preset="quality"]', name: 'quality'},
      ];
      for (let i = 0; i < presetButtons.length; i += 1) {
        const node = document.querySelector(presetButtons[i].selector);
        if (!node) continue;
        node.addEventListener('click', function () {
          applyPreset(presetButtons[i].name);
        });
      }

      const tabButtons = document.querySelectorAll('.tab-btn[data-tab]');
      tabButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
          switchTab(String(btn.getAttribute('data-tab') || 'overview'));
        });
      });

      const moduleTabButtons = document.querySelectorAll('.module-tab-btn');
      moduleTabButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
          switchModuleStudio(String(btn.getAttribute('data-module-tab') || 'story'));
        });
      });

      byId('queue_body').addEventListener('click', function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const action = target.getAttribute('data-action');
        const jobId = target.getAttribute('data-job-id');
        if (!action || !jobId) return;
        if (action === 'reprioritize') reprioritizeJob(jobId);
        if (action === 'cancel') cancelJob(jobId);
      });

      byId('config_versions_body').addEventListener('click', function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const action = target.getAttribute('data-action');
        if (action !== 'apply-config') return;
        const versionId = target.getAttribute('data-version-id');
        if (!versionId) return;
        applyConfigVersion(versionId);
      });

      function handleAlertAck(event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        if (target.getAttribute('data-action') !== 'ack-alert') return;
        const alertId = target.getAttribute('data-alert-id');
        if (!alertId) return;
        acknowledgeAlert(alertId);
      }

      byId('alert_list').addEventListener('click', handleAlertAck);
      byId('detail_alerts').addEventListener('click', handleAlertAck);

      byId('image_gallery').addEventListener('click', function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const action = target.getAttribute('data-action');
        if (action !== 'image-edit') return;
        const taskId = String(target.getAttribute('data-task-id') || '');
        if (!taskId) return;
        ui.imageDetailTaskId = taskId;
        const item = findImageByTaskId(taskId);
        populateImageDetail(item);
      });

      byId('image_gallery').addEventListener('change', function (event) {
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) return;
        const action = target.getAttribute('data-action');
        if (action !== 'image-select') return;
        const taskId = String(target.getAttribute('data-task-id') || '');
        if (!taskId) return;
        ui.imageSelectedTaskIds[taskId] = target.checked;
      });

      byId('module_jobs_body').addEventListener('click', function (event) {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const action = target.getAttribute('data-action');
        const jobId = String(target.getAttribute('data-job-id') || '');
        if (!action || !jobId) return;
        if (action === 'module-detail') {
          fetchModuleJobDetail(jobId, {log_limit: 400, event_limit: 260});
        }
        if (action === 'module-stop') {
          stopModuleJob(jobId);
        }
      });
    }


      // ----- NEW FEATURES -----
      async function fetchGallery(force) {
        if (!force && ui.activeTab !== 'gallery') return null;
        const cont = byId('gallery_container');
        if (!cont) return null;

        try {
          const data = await apiGet('/api/gallery');
          const images = Array.isArray(data && data.images) ? data.images : [];
          if (!images.length) {
            cont.innerHTML = '<div class="list-item">' + escapeHtml(t('msg.no_images_found', 'No images found.')) + '</div>';
            return data;
          }

          const cards = [];
          for (let i = 0; i < images.length; i += 1) {
            const img = images[i] || {};
            const title = String(img.title || '-');
            const category = String(img.category || '-');
            const age = String(img.age || '-');
            const modified = Number(img.modified);
            const modifiedText = Number.isFinite(modified)
              ? new Date(modified * 1000).toLocaleString()
              : '-';
            const cover = img.cover
              ? ('/api/images/file?path=' + encodeURIComponent(String(img.cover)))
              : '';

            const coverHtml = cover
              ? '<img class="gallery-cover" loading="lazy" src="' + escapeHtml(cover) + '" alt="' + escapeHtml(title) + '" />'
              : '<div class="gallery-cover" aria-hidden="true"></div>';

            cards.push(
              '<article class="gallery-card">' +
                coverHtml +
                '<div class="gallery-body">' +
                  '<div class="gallery-title">' + escapeHtml(title) + '</div>' +
                  '<div class="gallery-meta">' + escapeHtml(category + ' / ' + age) + '</div>' +
                  '<div class="gallery-meta">' + escapeHtml(modifiedText) + '</div>' +
                '</div>' +
              '</article>'
            );
          }
          cont.innerHTML = cards.join('');
          return data;
        } catch (_err) {
          cont.innerHTML = '<div class="list-item">' + escapeHtml(t('msg.no_images_found', 'No images found.')) + '</div>';
          return null;
        }
      }

      async function pollSystemStatus(force) {
        if (!force && ui.activeTab !== 'gallery') return null;
        try {
          const data = await apiGet('/api/system');
          const st = byId('sys-status');
          if (!st) return data;
          const ram = data && data.ram ? data.ram : {percent: 0};
          const gpus = Array.isArray(data && data.gpus) ? data.gpus : [];
          const gpuText = gpus.length
            ? gpus.map(function (g, i) { return 'GPU' + i + ': ' + String(g.gpu_util || 0) + '%'; }).join(' | ')
            : t('gallery.system.gpu_na', 'GPU: n/a');
          st.textContent = tf('gallery.system.status', {ram: String(ram.percent || 0), gpu: gpuText}, 'RAM: {ram}% | {gpu}');
          if (Number(ram.percent || 0) > 85) st.style.color = 'var(--danger)';
          else st.style.color = 'var(--accent)';
          return data;
        } catch (_err) {
          return null;
        }
      }

      function normalizeTemplateName(value) {
        return String(value || '').trim().toLowerCase();
      }

      async function saveTemplate() {
         const promptText = (byId('story_prompt').value || '').trim();
         if (!promptText) {
           setMessage(t('msg.prompt_empty', 'Prompt is empty.'), 'warn');
           return;
         }

         const nameInput = byId('template_name_input');
         const name = (nameInput && nameInput.value ? String(nameInput.value) : '').trim();
         if (!name) {
           setMessage(t('msg.template_name_required', 'Please enter a template name first.'), 'warn');
           if (nameInput) nameInput.focus();
           return;
         }

         const payload = {
           name: name,
           prompt: promptText,
           story_materials: String(byId('story_materials').value || '').trim(),
           story_input_mode: String(byId('story_input_mode').value || 'preset'),
         };

         setMessage(t('msg.saving_template', 'Saving template...'), 'ok');
         try {
           await apiPost('/api/templates/save', payload);
           await fetchTemplates(name);
           setMessage(t('msg.template_saved', 'Template saved.'), 'ok');
         } catch (err) {
           const text = (err && err.message) ? String(err.message) : t('msg.request_failed', 'Request failed');
           setMessage(t('msg.template_save_failed', 'Failed to save template.') + ' ' + text, 'bad');
         }
      }
      window.saveTemplate = saveTemplate;
      
      async function fetchTemplates(preferredName) {
         const select = byId('template_select');
         if (!select) return;

         const currentName = String(select.getAttribute('data-selected-name') || '').trim();
         const targetName = String(preferredName || currentName || '').trim();
         const targetNameNorm = normalizeTemplateName(targetName);
         const currentPrompt = String(byId('story_prompt').value || '');

         try {
           const data = await apiGet('/api/templates');
           const rows = Array.isArray(data) ? data : [];

           select.innerHTML = '';

           const defaultOption = document.createElement('option');
           defaultOption.value = '';
           defaultOption.textContent = t('template.placeholder', '-- Load a template --');
           select.appendChild(defaultOption);

           let selectedIndex = 0;
           for (let i = 0; i < rows.length; i += 1) {
             const item = rows[i] || {};
             const name = String(item.name || ('Template ' + String(i + 1))).trim();
             const prompt = String(item.prompt || '');
             const materials = String(item.story_materials || item.materials || '');
             const opt = document.createElement('option');

             opt.value = prompt;
             opt.textContent = name;
             opt.setAttribute('data-name', name);
             opt.setAttribute('data-prompt', prompt);
             opt.setAttribute('data-materials', materials);
             select.appendChild(opt);

             const optionIndex = i + 1;
             if (targetNameNorm && normalizeTemplateName(name) === targetNameNorm) {
               selectedIndex = optionIndex;
             } else if (!targetNameNorm && prompt && prompt === currentPrompt) {
               selectedIndex = optionIndex;
             }
           }

           select.selectedIndex = selectedIndex;
           const selected = select.options[selectedIndex] || null;
           if (selected && selectedIndex > 0) {
             select.setAttribute('data-selected-name', String(selected.getAttribute('data-name') || ''));
             const nameInput = byId('template_name_input');
             if (nameInput) nameInput.value = String(selected.getAttribute('data-name') || '');
           } else {
             select.removeAttribute('data-selected-name');
             const nameInput = byId('template_name_input');
             if (nameInput) nameInput.value = '';
           }
         } catch (err) {
           select.innerHTML = '';
           const defaultOption = document.createElement('option');
           defaultOption.value = '';
           defaultOption.textContent = t('template.placeholder', '-- Load a template --');
           select.appendChild(defaultOption);
         }
      }
      // -------------------------

    function init() {
      ui.language = getPreferredLanguage();
      applyLanguage();
      loadLocalForm();
      syncStoryInputMode();
      syncModuleStoryInputMode();
      fetchTemplates();
      pollSystemStatus(true);
      switchModuleStudio('story');
      loadHiddenModuleJobs();
      bindEvents();
      syncEvaluationSourceControls();
      updateEvaluationRunSelect();
      syncTranslationSourceLangByFolder();
      fetchTranslatableStories();
      restartTimer();
      refreshOverview(true);
      if (ui.activeTab === 'gallery') {
        fetchGallery(true);
      }
    }

    init();