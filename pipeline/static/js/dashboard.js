const STORE_KEY = 'genai.dashboard.form.v4';
    const LANG_STORE_KEY = 'genai.dashboard.lang.v1';
  const MODULE_HIDDEN_JOBS_KEY = 'genai.dashboard.modules.hidden_jobs.v1';

    const I18N = {
      'en': {
        'title.dashboard': 'GenAI Chief Control Plane',
        'hero.eyebrow': 'GenAI Operations',
        'hero.title': 'Chief Control Plane',
        'hero.sub': 'Operate runs, inspect alerts, manage queue priority, and audit production history from one dashboard.',
        'page.overview.title': 'Generate',
        'page.overview.sub': 'Compare KG-guided and user-controlled generation, then capture live evidence from one screen.',
        'page.ops.title': 'Operations',
        'page.ops.sub': 'Inspect queue pressure, alert activity, capacity, and saved config versions.',
        'page.detail.title': 'Run Detail',
        'page.detail.sub': 'Review one run end-to-end, including timeline, alerts, artifacts, and logs.',
        'page.evaluation.title': 'Evaluation',
        'page.evaluation.sub': 'Inspect assessment reports, radar dimensions, and key findings for one story output.',
        'page.gallery.title': 'Gallery',
        'page.gallery.sub': 'Browse generated stories with cover previews and inspect freshness, coverage, and metadata at a glance.',
        'page.modules.title': 'Modules',
        'page.modules.sub': 'Run text, image, translation, voice, and general tools independently from the main pipeline.',
        'label.auto_refresh': 'Auto refresh',
        'label.language': 'Language',
        'kpi.system_state': 'Run State',
        'kpi.queue_depth': 'Queue',
        'kpi.success_rate': 'Success Rate',
        'kpi.avg_duration': 'Avg Duration',
        'kpi.gpu_cost': 'Est. GPU Cost',
        'kpi.progress': 'Progress',
        'kpi.elapsed': 'Elapsed',
        'kpi.updated': 'Last Update',
        'tab.overview': 'Generate',
        'tab.ops': 'Operations',
        'tab.detail': 'Run Detail',
        'tab.evaluation': 'Evaluation',
        'tab.modules': 'Modules',
        'label.tab_gallery': 'Gallery',
        'gallery.title': 'Story Gallery',
        'gallery.sub': 'Browse generated stories with cover previews and quick metadata.',
        'gallery.snapshot.title': 'Gallery Snapshot',
        'gallery.snapshot.hint': 'Use this summary to spot freshness gaps and missing covers without leaving the gallery.',
        'gallery.snapshot.total': 'Stories',
        'gallery.snapshot.covers': 'Covers',
        'gallery.snapshot.categories': 'Categories',
        'gallery.snapshot.latest': 'Latest Update',
        'gallery.snapshot.highlights': 'Highlights',
        'gallery.snapshot.empty': 'Load the gallery to see freshness and cover coverage.',
        'gallery.snapshot.latest_none': 'No gallery data yet.',
        'gallery.snapshot.missing_covers': 'Missing covers: {count}',
        'gallery.snapshot.top_category': 'Top category: {name} ({count})',
        'gallery.snapshot.age_mix': 'Age mix: {ages}',
        'gallery.system_title': 'Resource Snapshot',
        'gallery.system_hint': 'Same live telemetry as Generate, kept here for quick checks while browsing results.',
        'gallery.empty.title': 'No stories to preview yet.',
        'gallery.empty.copy': 'Generated covers and story cards will appear here after the first successful run.',
        'gallery.system.status_limited': 'CPU: n/a | RAM: {ram}% | {gpu}',
        'overview.composer.title': 'Run Composer',
        'overview.composer.sub': 'Configure the thesis demo from left to right: scope, KG or user control, pipeline strategy, and launch.',
        'demo.storyline.title': 'Demo Storyline',
        'demo.storyline.sub': 'Use this order for a concise thesis demo: baseline, controlled generation, modular rerun, then evaluation.',
        'demo.storyline.focus.step1': 'Step 1',
        'demo.storyline.focus.step2': 'Step 2',
        'demo.storyline.focus.step3': 'Step 3',
        'demo.storyline.focus.step4': 'Step 4',
        'demo.storyline.hint': 'Recommended recording flow: preset run, custom rerun, one module-only regeneration, then evaluation summary.',
        'demo.step1.title': 'KG baseline',
        'demo.step1.copy': 'Stay in preset mode to show how age, category, theme, and subcategory are filled by KG defaults.',
        'demo.step2.title': 'Controlled generation',
        'demo.step2.copy': 'Switch to custom mode, add prompt and materials, then explain that user intent is normalized under KG constraints.',
        'demo.step3.title': 'Module proof',
        'demo.step3.copy': 'Use Text, Image, Translation, or Voice Studio to rerun only one layer instead of the whole pipeline.',
        'demo.step4.title': 'Evaluation evidence',
        'demo.step4.copy': 'Finish in Evaluation to discuss quality metrics, findings, and how changes affected the final output.',
        'btn.demo_generate': 'Focus Generate',
        'btn.demo_modules': 'Open Modules',
        'btn.demo_evaluation': 'Open Evaluation',
        'kg.summary.title': 'Generation Logic Snapshot',
        'kg.summary.sub': 'Summarize how KG defaults, user control, runtime strategy, and saved artifacts will shape the current run.',
        'kg.summary.label.mode': 'Input Mode',
        'kg.summary.label.source': 'Control Source',
        'kg.summary.label.scope': 'Story Scope',
        'kg.summary.label.plan': 'Model Plan',
        'kg.summary.mode_preset': 'Preset',
        'kg.summary.mode_custom': 'Custom',
        'kg.summary.source_preset': 'KG defaults',
        'kg.summary.source_custom': 'KG + normalized user intent',
        'kg.summary.scope': '{age} / {category}',
        'kg.summary.hint': 'Keep the full graph as supporting evidence. In the main dashboard, show only the logic summary that directly affects the generated story.',
        'kg.summary.point.preset': 'Preset mode exposes the KG prior directly. Highlight the selected age, category, theme, and subcategory as the baseline condition.',
        'kg.summary.point.custom': 'Custom mode keeps KG safety and age appropriateness, but merges normalized prompt and materials intent into the final guidelines.',
        'kg.summary.point.outputs': 'Enabled output chain: {outputs}. Use this to explain which stages are expected to appear in the final demo artifact.',
        'kg.summary.point.evidence_preset': 'Evidence files to mention after generation: kg_profile.json, character_bible.json, world_style_lock.json, and story_meta.json.',
        'kg.summary.point.evidence_custom': 'Evidence files to mention after generation: kg_guidelines.txt, normalized user intent, and the final story_meta.json.',
        'kg.summary.point.scope_preset': 'Theme: {theme} | Subcategory: {subcategory} | Preset mode bypasses prompt conversion.',
        'kg.summary.point.scope_custom': 'Theme: {theme} | Subcategory: {subcategory} | Prompts: {prompts} | Materials: {materials}',
        'kg.summary.pill_preset': 'KG',
        'kg.summary.pill_custom': 'KG + User',
        'overview.telemetry.title': 'Live Telemetry',
        'overview.resource.cpu': 'CPU',
        'overview.resource.ram': 'RAM',
        'overview.resource.gpu': 'GPU',
        'overview.resource.vram': 'VRAM',
        'overview.resource.cpu_value': '{value}% of {count} threads',
        'overview.resource.ram_value': '{used} / {total} GB ({pct}%)',
        'overview.resource.gpu_value': '{value}% | {name}',
        'overview.resource.vram_value': '{used} / {total} GB ({pct}%)',
        'overview.resource.gpu_na': 'n/a',
        'overview.resource.detail': '{accelerator} | updated {time}',
        'overview.resource.detail_na': 'System telemetry unavailable.',
        'overview.resource.detail_limited': '{accelerator} | limited telemetry',
        'overview.resource.metric_unavailable': 'n/a',
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
        'overview.field.model_plan': 'Model Plan',
        'overview.field.config_version_name': 'Config Version Name',
        'overview.field.version_note': 'Version Note',
        'overview.toggle.photo': 'Photo',
        'overview.toggle.translation': 'Translation',
        'overview.toggle.voice': 'Voice',
        'overview.toggle.verify': 'Verify',
        'overview.toggle.low_vram': 'Low VRAM',
        'overview.toggle.strict_translation': 'Translation required',
        'overview.toggle.strict_voice': 'Voice required',
        'overview.strict_modes.hint': 'If required, that stage must succeed or the book is marked failed. Turn it off to allow degraded output.',
        'overview.preset.balanced': 'Balanced',
        'overview.preset.speed': 'Speed',
        'overview.preset.quality': 'Quality',
        'overview.quick_profile.label': 'Workflow Preset',
        'overview.quick_profile.hint': 'Workflow presets change model plan plus retries, stage toggles, and required-stage behavior.',
        'overview.model_plan.hint': 'Auto chooses a model profile from the current hardware. Workflow presets also update this field.',
        'overview.model_plan.scope_hint': 'Use this only when you want to change model/hardware strategy without changing the rest of the workflow.',
        'overview.model_plan.selected': 'Selected: {plan}',
        'overview.model_plan.recommended': 'Auto recommends: {plan}',
        'overview.model_plan.hardware': '{accelerator} | VRAM {vram} GB | RAM {ram} GB',
        'overview.model_plan.hardware_unknown': 'Hardware detection unavailable',
        'overview.model_plan.unknown': 'Unknown',
        'overview.model_plan.auto': 'Auto',
        'overview.model_plan.balanced': 'Balanced',
        'overview.model_plan.portable': 'Portable',
        'overview.model_plan.quality': 'Quality',
        'overview.model_plan.cpu': 'CPU Safe',
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
        'overview.process.title': 'Run Context',
        'overview.process.pid': 'PID',
        'overview.process.stage': 'Stage',
        'overview.process.book': 'Book',
        'overview.process.updated': 'Updated',
        'overview.process.uptime': 'Uptime',
        'overview.meta.run_id': 'Run ID',
        'overview.meta.pid': 'PID',
        'overview.meta.exit_code': 'Exit Code',
        'overview.meta.queue_depth': 'Queue Depth',
        'overview.monitor.summary.running': 'Run in progress',
        'overview.monitor.summary.ready': 'Ready for the next run',
        'overview.monitor.summary.queued': 'Queue pending',
        'overview.monitor.summary.postrun': 'Last run {state}',
        'overview.monitor.copy.running': 'Run {run_id} is active at {stage}.',
        'overview.monitor.copy.running_compact': 'Review the active book, stage, and pre-evaluation below.',
        'overview.monitor.copy.ready': 'Adjust the composer on the left, then start or queue a run.',
        'overview.monitor.copy.queued': 'No active run right now. {count} job(s) remain in queue.',
        'overview.monitor.copy.postrun': 'Last run {run_id} ended in {state}. Review the summary below before starting again.',
        'overview.monitor.copy.postrun_compact': 'Review the latest run summary below before starting again.',
        'overview.monitor.side.progress': 'Progress',
        'overview.monitor.side.queue': 'Queue',
        'overview.monitor.side.elapsed': 'Elapsed',
        'overview.monitor.side.updated': 'Last update',
        'overview.monitor.side.pressure': 'Pressure',
        'overview.monitor.last_run.title': 'Latest Run',
        'overview.monitor.last_run.none': 'No recent run summary yet.',
        'overview.monitor.last_run.result': 'Result',
        'overview.monitor.last_run.books': 'Books',
        'overview.monitor.next.title': 'Next Step',
        'overview.monitor.next.ready': 'Configure the next run from the composer on the left.',
        'overview.monitor.next.review': 'Review the previous run if needed, then adjust settings and start again.',
        'overview.monitor.next.queued': 'A queued job is waiting. You can still adjust future runs on the left.',
        'overview.monitor.next.queue': 'Queue depth: {count}',
        'overview.monitor.next.plan': 'Model plan: {selected} | Auto: {recommended}',
        'overview.monitor.next.pressure': 'Resource pressure: {value}',
        'overview.monitor.result.ready': 'Ready',
        'overview.advisory.issues': 'Current Issues',
        'health.process.detail.chief_resources': 'PID {pid} | CPU {cpu}% | RAM {ram} GB | {cache}',
        'ops.queue.title': 'Queue and Priority',
        'ops.alert.title': 'Alert Center',
        'ops.alert.hint': 'Alerts include queue pressure, repeated failures, and run-stop incidents.',
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
        'eval.branch': 'Report Variant',
        'eval.branch_hint': 'Use the report variant name. In most cases, keep `canonical`.',
        'eval.advanced.show': 'Advanced options',
        'eval.advanced.hide': 'Hide advanced',
        'eval.advanced.custom': 'Advanced: {value}',
        'eval.overall': 'Overall Score',
        'eval.scope': 'Scope',
        'eval.branch_used': 'Report Variant',
        'eval.report_file': 'Report File',
        'eval.meta.source': 'Source',
        'eval.meta.run_id': 'Run ID',
        'eval.meta.story_root': 'Story Root',
        'eval.chart.title': 'Dimension Radar',
        'eval.chart.empty.title': 'No evaluation chart yet.',
        'eval.chart.empty.copy': 'Load a story report to compare dimension scores on the radar chart.',
        'eval.log.title': 'Assessment JSON',
        'module.jobs.title': 'Module Jobs',
        'module.job_detail.title': 'Module Job Detail',
        'module.job_events.title': 'Events',
        'module.job_logs.title': 'Logs',
        'module.workbenches.title': 'Module Workbenches',
        'module.workbenches.sub': 'Run text, image, translation, and voice independently without executing the full pipeline.',
        'module.demo.sub': 'Use this area to prove that the system supports local regeneration: change one layer, keep the rest of the pipeline intact.',
        'btn.module_focus_story': 'Text proof',
        'btn.module_focus_image': 'Image proof',
        'btn.module_focus_eval': 'Open Evaluation',
        'module.demo.story.title': '1. Freeze the story draft',
        'module.demo.story.copy': 'Run Text Studio first to create the baseline story, then use the resulting story root as the anchor for later comparisons.',
        'module.demo.image.title': '2. Regenerate one modality only',
        'module.demo.image.copy': 'Move to Image, Translation, or Voice Studio and rerun only the weak layer to show controllability without recomputing everything.',
        'module.demo.eval.title': '3. Close the loop with evidence',
        'module.demo.eval.copy': 'After a module rerun, open Evaluation or Gallery to compare whether the edited layer actually improved the final artifact.',
        'module.tab.story': 'Text Studio',
        'module.tab.image': 'Image Studio',
        'module.tab.translation': 'Translation Studio',
        'module.tab.voice': 'Voice Studio',
        'module.tab.general': 'General Studio',
        'module.studio.story.title': 'Text Studio',
        'module.studio.story.sub': 'Generate standalone story drafts and queue text-only runs without touching images or voice.',
        'module.studio.image.title': 'Image Studio',
        'module.studio.image.sub': 'Inspect existing image tasks, tweak prompts, and rerun only the visual layer for a story.',
        'module.studio.translation.title': 'Translation Studio',
        'module.studio.translation.sub': 'Translate existing story outputs, choose target languages, and rerun translation independently.',
        'module.studio.voice.title': 'Voice Studio',
        'module.studio.voice.sub': 'Generate narration from an existing story root, with direct control over speaker samples and page ranges.',
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
        'btn.acknowledge': 'Dismiss',
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
        'msg.compatibility_limited': 'Compatibility mode: {items} unavailable in the current backend. Restart dashboard after the current run.',
        'msg.capability.queue': 'queue',
        'msg.capability.alerts': 'alerts',
        'msg.capability.capacity': 'capacity analytics',
        'msg.capability.configs': 'config versions',
        'msg.capability.process_telemetry': 'process telemetry',
        'msg.queue_unavailable': 'Queue data is unavailable in the current backend.',
        'msg.alerts_unavailable': 'Alert data is unavailable in the current backend.',
        'msg.capacity_unavailable': 'Capacity analytics are unavailable in the current backend.',
        'msg.configs_unavailable': 'Config versions are unavailable in the current backend.',
        'ops.summary.hint_unavailable': 'Historical capacity metrics are unavailable in the current backend.',
        'ops.summary.health_limited': 'Limited',
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
        'msg.select_story_root_for_images': 'Load a story root or wait for image generation to populate this grid.',
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
        'msg.failed_ack_alert': 'Failed to dismiss alert.',
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
        'placeholder.voice_script': 'Read 3 to 5 calm, natural sentences with one line of narration, one short line of dialogue, and one clear pause.',
        'placeholder.theme_custom': 'ex: friendship, courage, mystery',
        'placeholder.subcategory_custom': 'ex: forest, tradition, science',
        'placeholder.speaker_dir': 'ex: models/XTTS-v2/samples/custom',
        'placeholder.evaluation_branch': 'canonical',
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
      'kpi.progress': '進度',
      'kpi.elapsed': '已耗時',
      'kpi.updated': '更新延遲',
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
        'gallery.system.status': 'CPU?{cpu}% | RAM?{ram}% | {gpu}',
        'gallery.system.status_limited': 'CPU：無資料 | RAM：{ram}% | {gpu}',
        'gallery.system.gpu_na': 'GPU：無資料',
        'gallery.system.status': 'CPU?{cpu}% | RAM?{ram}% | {gpu}',
        'overview.composer.title': '主流程生成設定',
        'overview.composer.sub': '依照論文 demo 的敘事順序設定：範圍、KG 或使用者控制、流程策略，最後啟動。',
        'demo.storyline.title': 'Demo 腳本',
        'demo.storyline.sub': '建議用這個順序完成論文展示：基準版、可控生成、模組重生成，最後進入評估。',
        'demo.storyline.focus.step1': '步驟 1',
        'demo.storyline.focus.step2': '步驟 2',
        'demo.storyline.focus.step3': '步驟 3',
        'demo.storyline.focus.step4': '步驟 4',
        'demo.storyline.hint': '建議錄影流程：先跑 preset 基準版，再跑 custom 控制版，接著做一次模組單層重生成，最後用評估頁收尾。',
        'demo.step1.title': 'KG 基準版',
        'demo.step1.copy': '先停留在預設模式，說明年齡、類別、主題與子類別如何由 KG 預設驅動。',
        'demo.step2.title': '可控生成',
        'demo.step2.copy': '切換到自訂模式，加入 prompt 與 materials，說明使用者需求會在 KG 約束下被正規化後合併。',
        'demo.step3.title': '模組化證明',
        'demo.step3.copy': '進入 Text、Image、Translation 或 Voice Studio，只重跑單一層，證明不必整條 pipeline 重算。',
        'demo.step4.title': '評估證據',
        'demo.step4.copy': '最後切到 Evaluation，用品質分數與觀察結果說明修改如何影響最終輸出。',
        'btn.demo_generate': '回到生成頁',
        'btn.demo_modules': '打開模組頁',
        'btn.demo_evaluation': '打開評估頁',
        'kg.summary.title': '生成邏輯摘要',
        'kg.summary.sub': '用這張卡片快速說明：目前這次生成是如何同時受到 KG 預設、使用者控制、執行策略與輸出證據影響。',
        'kg.summary.label.mode': '輸入模式',
        'kg.summary.label.source': '控制來源',
        'kg.summary.label.scope': '故事範圍',
        'kg.summary.label.plan': '模型計畫',
        'kg.summary.mode_preset': '預設',
        'kg.summary.mode_custom': '自訂',
        'kg.summary.source_preset': '僅 KG 預設',
        'kg.summary.source_custom': 'KG + 正規化使用者意圖',
        'kg.summary.scope': '{age} / {category}',
        'kg.summary.hint': '完整圖譜建議保留在輔助畫面。主 dashboard 只顯示會直接影響故事生成的邏輯摘要即可。',
        'kg.summary.point.preset': '預設模式最適合展示 KG 先驗。請強調目前選到的年齡、類別、主題與子類別就是基準條件。',
        'kg.summary.point.custom': '自訂模式仍保留 KG 的安全性與年齡適配，但會把 prompt 與 materials 正規化後合併進最終 guidelines。',
        'kg.summary.point.outputs': '目前啟用的輸出鏈：{outputs}。可用來說明最後 demo 會展示哪些模組結果。',
        'kg.summary.point.evidence_preset': '生成後可展示的證據檔案：kg_profile.json、character_bible.json、world_style_lock.json、story_meta.json。',
        'kg.summary.point.evidence_custom': '生成後可展示的證據檔案：kg_guidelines.txt、正規化後的使用者意圖，以及最終 story_meta.json。',
        'kg.summary.point.scope_preset': '主題：{theme} | 子類別：{subcategory} | 預設模式不會經過 prompt 轉換層。',
        'kg.summary.point.scope_custom': '主題：{theme} | 子類別：{subcategory} | Prompt 數：{prompts} | 素材數：{materials}',
        'kg.summary.pill_preset': 'KG',
        'kg.summary.pill_custom': 'KG + 使用者',
        'overview.telemetry.title': '即時執行監控',
        'overview.resource.cpu': 'CPU',
        'overview.resource.ram': 'RAM',
        'overview.resource.gpu': 'GPU',
        'overview.resource.vram': 'VRAM',
        'overview.resource.cpu_value': '?? {count} ????? {value}%',
        'overview.resource.ram_value': '{used} / {total} GB ({pct}%)',
        'overview.resource.gpu_value': '{name} | {value}%',
        'overview.resource.vram_value': '{used} / {total} GB ({pct}%)',
        'overview.resource.gpu_na': '???',
        'overview.resource.detail': '{accelerator} | {gpus} | ?? {time}',
        'overview.resource.detail_na': '?????????????',
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
        'overview.field.model_plan': '模型方案',
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
        'overview.model_plan.hint': 'Auto 會依目前硬體自動選擇模型方案，套用預設時也會同步更新這個欄位。',
        'overview.model_plan.selected': '目前選擇：{plan}',
        'overview.model_plan.recommended': 'Auto 建議：{plan}',
        'overview.model_plan.hardware': '{accelerator} | VRAM {vram} GB | RAM {ram} GB',
        'overview.model_plan.hardware_unknown': '目前無法偵測硬體資訊',
        'overview.model_plan.unknown': '未知',
        'overview.model_plan.auto': '自動',
        'overview.model_plan.balanced': '平衡',
        'overview.model_plan.portable': '速度 / 可攜',
        'overview.model_plan.quality': '品質',
        'overview.model_plan.cpu': 'CPU 安全',
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
      'overview.process.pid': 'PID',
      'overview.process.stage': '階段',
      'overview.process.updated': '更新延遲',
      'overview.meta.run_id': 'Run ID',
        'overview.meta.pid': 'PID',
        'overview.meta.exit_code': '結束代碼',
        'overview.meta.queue_depth': '佇列深度',
        'ops.queue.title': '佇列與優先序',
        'ops.alert.title': '警示中心',
        'ops.alert.hint': '這裡會顯示佇列壓力、連續失敗與執行中斷等警示。',
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
        'eval.branch': '報告版本',
        'eval.branch_hint': '這是評估報告的版本名稱；大多數情況保持 `canonical` 即可。',
        'eval.advanced.show': '進階選項',
        'eval.advanced.hide': '收合進階選項',
        'eval.advanced.custom': '進階選項：{value}',
        'eval.overall': '總分',
        'eval.scope': '評估範圍',
        'eval.branch_used': '報告版本',
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
        'module.workbenches.sub': '在不執行整條主流程的情況下，獨立重跑文字、圖片、翻譯與語音模組。',
        'module.demo.sub': '這一區用來證明系統支援局部重生成：只改一層，其他流程保持不變。',
        'btn.module_focus_story': '文字證明',
        'btn.module_focus_image': '圖片證明',
        'btn.module_focus_eval': '打開評估頁',
        'module.demo.story.title': '1. 先固定故事草稿',
        'module.demo.story.copy': '先用 Text Studio 生成基準故事，再把得到的 story root 當作後續比較的錨點。',
        'module.demo.image.title': '2. 只重生單一模態',
        'module.demo.image.copy': '切到 Image、Translation 或 Voice Studio，只重跑較弱的那一層，展示可控性與效率。',
        'module.demo.eval.title': '3. 用證據收尾',
        'module.demo.eval.copy': '模組重跑後，切到 Evaluation 或 Gallery，比較局部修改是否真的改善最終成品。',
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
        'btn.acknowledge': '忽略',
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
        'msg.failed_ack_alert': '忽略警示失敗。',
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
        'placeholder.voice_script': '請用自然、穩定的語氣錄 3 到 5 句，包含旁白、一句對話和一次明顯停頓。',
        'placeholder.theme_custom': '例如：友情、勇氣、冒險',
        'placeholder.subcategory_custom': '例如：森林、傳統、科學',
        'placeholder.speaker_dir': '例如：models/XTTS-v2/samples/custom',
        'placeholder.evaluation_branch': 'canonical（通常不用改）',
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

    Object.assign(I18N['zh-TW'], {
      'overview.system.title': '系統資源',
      'overview.process.title': '目前執行程序',
      'overview.advisory.title': '執行建議',
      'ops.summary.title': '營運摘要',
      'ops.summary.active': '目前主流程',
      'ops.summary.queue': '排隊任務',
      'ops.summary.alerts': '未處理警示',
      'ops.summary.modules': '模組任務',
      'ops.summary.health': '營運健康度',
      'ops.summary.running_job': '執行中 {job}',
      'ops.summary.hint_dynamic': '成功率 {success} | 平均排隊延遲 {delay} | GPU 成本 {cost}',
      'detail.artifact.story_root': '故事目錄',
      'detail.artifact.book': '目前書本',
      'detail.artifact.stage': '最後階段',
      'detail.artifact.eval': '評估狀態',
      'detail.artifact.eval_ready': '已就緒',
      'detail.artifact.eval_pending': '未就緒',
      'eval.insight.title': '評估洞察',
      'eval.insight.empty_summary': '尚未載入評估資料。',
      'eval.insight.empty_findings': '重點觀察會顯示在這裡。',
      'eval.insight.strongest': '最佳維度',
      'eval.insight.strongest_detail': '{name} 分數為 {score}。',
      'eval.insight.weakest': '待加強維度',
      'eval.insight.weakest_detail': '{name} 分數為 {score}。',
      'eval.insight.scope': '目前評估範圍',
      'eval.insight.scope_detail': '書本 {book}，來源 {story_root}',
      'eval.insight.issues': '問題',
      'eval.insight.warnings': '警示',
      'eval.insight.findings': '觀察',
      'eval.insight.recommendations': '建議',
      'module.summary.title': '模組摘要',
      'module.summary.active': '執行中任務',
      'module.summary.pending': '等待中任務',
      'module.summary.history': '可見紀錄',
      'module.summary.selected': '目前選取',
      'module.summary.none': '無',
      'module.summary.hint_dynamic': '歷史紀錄 {history} | 已隱藏 {hidden} | 執行中類型 {type}',
      'btn.recommended': '建議組合',
      'btn.select_all': '全選',
      'overview.strict_modes.hint': '嚴格翻譯或嚴格語音代表該階段一旦失敗，這本書會直接記為失敗，而不是降級完成。',
      'overview.quick_profile.label': '快捷方案',
      'overview.quick_profile.hint': '快捷方案會一起調整模型方案、重試次數、階段開關與嚴格模式。',
      'overview.model_plan.scope_hint': '如果你只想改模型與硬體策略、不想動其他流程設定，改這裡就好。',
      'health.level.stable': '穩定',
      'health.level.warning': '警示',
      'health.level.critical': '危急',
      'health.level.info': '資訊',
      'health.model_cache.empty': '模型快取：空',
      'health.model_cache.summary': '模型快取：{items}',
      'health.model_cache.state.ready': '待命',
      'health.model_cache.state.busy': '使用中',
      'health.model_cache.state.offloaded': '已卸載',
      'health.process.active': 'chief 執行中',
      'health.process.idle': '閒置',
      'health.process.none': '目前沒有執行中的主流程程序。',
      'health.process.metric_limited': '受限',
      'health.process.detail.chief': 'PID {pid} | {name} | {cache}',
      'health.process.detail.chief_limited': 'PID {pid} | {name} | 目前後端的程序遙測受限 | {cache}',
      'health.process.detail.dashboard': 'Dashboard PID {pid} | {cache}',
      'health.advisory.telemetry_missing.title': '系統遙測尚未就緒',
      'health.advisory.telemetry_missing.detail': '目前還沒有可用的資源使用資料。',
      'health.advisory.memory_high.title': '記憶體壓力過高',
      'health.advisory.memory_high.detail': 'VRAM 或 RAM 已超過 92%，建議切換可攜方案或暫停重型階段。',
      'health.advisory.memory_warn.title': '資源壓力偏高',
      'health.advisory.memory_warn.detail': '目前工作負載已接近系統上限。',
      'health.advisory.heartbeat_stale.title': '執行心跳過久未更新',
      'health.advisory.heartbeat_stale.detail': '狀態檔已 {seconds} 秒沒有更新。',
      'health.advisory.heartbeat_slow.title': '執行更新速度變慢',
      'health.advisory.heartbeat_slow.detail': '狀態更新速度低於預期。',
      'overview.resource.detail_limited': '{accelerator} | {gpus} | 遙測資料受限',
      'overview.resource.metric_unavailable': '受限',
      'health.advisory.chief_missing.title': '找不到 chief 程序',
      'health.advisory.chief_missing.detail': 'Dashboard 顯示主流程執行中，但目前偵測不到 chief 程序。',
      'health.advisory.queue_pressure.title': '佇列深度正在上升',
      'health.advisory.queue_pressure.detail': '可能需要調整優先序，或改用成本較低的方案。',
      'health.advisory.gpu_missing.title': '未偵測到 GPU',
      'health.advisory.gpu_missing.detail': '圖片階段在純 CPU 環境下會明顯變慢。',
      'health.advisory.plan_override.title': '目前方案覆蓋了硬體建議',
      'health.advisory.plan_override.detail': '目前選擇為 {selected}，Auto 建議為 {recommended}。',
      'health.advisory.ready': '系統狀態正常，目前設定與資源餘裕相符。',
      'health.summary.ready': '系統已準備好進行下一次生成。',
      'health.summary.running_healthy': '主流程執行中，資源餘裕看起來正常。',
      'health.run_context.active': 'Run {run_id} | {stage}',
      'health.run_context.idle': '目前沒有主流程執行中',
      'health.pressure.low': '低',
      'health.pressure.moderate': '中',
      'health.pressure.elevated': '偏高',
      'health.pressure.critical': '危急',
      'health.meta.plan': '方案：{selected} | Auto：{recommended}',
      'health.meta.run': '執行：{text}',
      'health.meta.pressure': '壓力：{value}',
    });

    Object.assign(I18N['zh-TW'], {
      'kpi.system_state': '執行狀態',
      'kpi.queue_depth': '佇列',
      'kpi.updated': '最後更新',
      'gallery.system_title': '資源快照',
      'gallery.system_hint': '這裡顯示和 Generate 相同的即時遙測，方便瀏覽成果時快速查看資源狀況。',
      'overview.resource.metric_unavailable': '無資料',
      'overview.toggle.strict_translation': '翻譯必須成功',
      'overview.toggle.strict_voice': '語音必須成功',
      'overview.strict_modes.hint': '開啟後，該階段失敗就會讓整本書記為失敗；關閉時則允許降級完成。',
      'overview.quick_profile.label': '工作流預設',
      'overview.quick_profile.hint': '工作流預設會一起調整模型方案、重試次數、階段開關與必須成功的階段。',
      'overview.model_plan.hint': 'Auto 會依目前硬體自動選擇模型方案；套用工作流預設時也會同步更新這個欄位。',
      'overview.model_plan.scope_hint': '如果你只想調整模型與硬體策略，不想改其他流程設定，就改這裡。',
      'ops.summary.hint_dynamic': '成功率 {success} | 平均排隊延遲 {delay} | GPU 成本 {cost}',
      'ops.summary.hint_unavailable': '目前後端不支援歷史容量統計。',
      'ops.summary.health_limited': '受限',
      'health.process.metric_limited': '無資料',
      'health.process.detail.chief_limited': 'PID {pid} | {name} | 目前後端只提供 PID 與階段資訊 | {cache}',
      'msg.compatibility_limited': '相容模式：目前後端不支援 {items}。請在這次執行結束後重啟 dashboard。',
      'msg.capability.queue': '佇列',
      'msg.capability.alerts': '警示',
      'msg.capability.capacity': '容量統計',
      'msg.capability.configs': '設定版本',
      'msg.capability.process_telemetry': '程序遙測',
      'msg.queue_unavailable': '目前後端無法提供佇列資料。',
      'msg.alerts_unavailable': '目前後端無法提供警示資料。',
      'msg.capacity_unavailable': '目前後端無法提供容量統計資料。',
      'msg.configs_unavailable': '目前後端無法提供設定版本資料。',
    });

    Object.assign(I18N['zh-TW'], {
      'page.overview.title': '故事生成',
      'page.overview.sub': '在同一個頁面比較 KG 引導與使用者控制生成，並同步蒐集 demo 證據。',
      'page.ops.title': '營運中心',
      'page.ops.sub': '集中查看佇列、警示、容量與設定版本，適合排程與營運管理。',
      'page.detail.title': '執行明細',
      'page.detail.sub': '追蹤單次 run 的時間線、警示、產物與完整日誌。',
      'page.evaluation.title': '評估診斷',
      'page.evaluation.sub': '檢視單一本故事的評估報告、維度雷達與重點發現。',
      'page.gallery.title': '作品圖庫',
      'page.gallery.sub': '快速瀏覽已生成的故事與封面，並同步查看當前資源壓力。',
      'page.modules.title': '模組工作台',
      'page.modules.sub': '將文字、圖片、翻譯、語音與通用工具拆開單獨執行。',
      'gallery.empty.title': '目前還沒有可預覽的作品。',
      'gallery.empty.copy': '第一批生成完成後，這裡會顯示封面卡片與故事摘要。',
      'eval.chart.empty.title': '目前沒有可顯示的雷達圖。',
      'eval.chart.empty.copy': '先載入一份評估報告，這裡才會顯示各維度分數。',
      'module.studio.story.title': '文字工作台',
      'module.studio.story.sub': '單獨生成故事草稿或排入文字模組任務，不影響圖片與語音。',
      'module.studio.image.title': '圖片工作台',
      'module.studio.image.sub': '檢查既有圖片任務、調整 prompt，並只重跑視覺層。',
      'module.studio.translation.title': '翻譯工作台',
      'module.studio.translation.sub': '針對既有故事輸出執行翻譯，獨立選擇目標語言與翻譯參數。',
      'module.studio.voice.title': '語音工作台',
      'module.studio.voice.sub': '從既有故事目錄產生旁白，直接控制 speaker sample 與頁碼範圍。',
      'msg.select_story_root_for_images': '先載入故事目錄，或等待圖片生成完成後再回到這裡查看。',
    });

    Object.assign(I18N['zh-TW'], {
      'overview.monitor.summary.running': '主流程執行中',
      'overview.monitor.summary.ready': '系統已準備好進行下一次生成',
      'overview.monitor.summary.queued': '佇列中仍有待處理任務',
      'overview.monitor.summary.postrun': '上一次執行為 {state}',
      'overview.monitor.copy.running': 'Run {run_id} 目前停在 {stage}。',
      'overview.monitor.copy.ready': '左側完成設定後，就可以直接開始或加入佇列。',
      'overview.monitor.copy.queued': '目前沒有 active run，但佇列中還有 {count} 個任務待處理。',
      'overview.monitor.copy.postrun': '上一個 Run {run_id} 已結束，結果為 {state}。重新開始前先看一次摘要會比較安全。',
      'overview.monitor.side.progress': '進度',
      'overview.monitor.side.queue': '佇列',
      'overview.monitor.side.elapsed': '已耗時',
      'overview.monitor.side.updated': '最後更新',
      'overview.monitor.side.pressure': '壓力',
      'overview.monitor.last_run.title': '最近一次執行',
      'overview.monitor.last_run.none': '目前沒有可用的最近執行摘要。',
      'overview.monitor.last_run.result': '結果',
      'overview.monitor.last_run.books': '書本',
      'overview.monitor.next.title': '下一步',
      'overview.monitor.next.ready': '先在左側調整這次要跑的設定，再開始或加入佇列。',
      'overview.monitor.next.review': '先確認上一個 run 的結果，再調整設定後重新開始。',
      'overview.monitor.next.queued': '佇列裡還有待跑任務；你現在可以繼續調整下一次的設定。',
      'overview.monitor.next.queue': '佇列深度：{count}',
      'overview.monitor.next.plan': '模型方案：{selected} | Auto 建議：{recommended}',
      'overview.monitor.next.pressure': '目前資源壓力：{value}',
      'overview.monitor.result.ready': '待命',
      'overview.advisory.issues': '目前問題',
    });

    Object.assign(I18N['zh-TW'], {
      'overview.resource.detail': '{accelerator} | 已更新 {time}',
      'overview.resource.detail_limited': '{accelerator} | 遙測資料受限',
      'overview.process.title': '執行摘要',
      'overview.process.stage': '階段',
      'overview.process.book': '書本',
      'overview.process.updated': '最後更新',
      'overview.process.uptime': '已執行時間',
      'health.process.active': '主流程執行中',
      'health.process.idle': '待命',
      'health.process.none': '目前沒有執行中的主流程。',
      'health.process.detail.chief_resources': 'PID {pid} | CPU {cpu}% | RAM {ram} GB | {cache}',
      'health.process.detail.chief_limited': 'PID {pid} | {name} | 以執行內容為主的摘要模式 | {cache}',
    });

    Object.assign(I18N['zh-TW'], {
      'page.gallery.sub': '瀏覽已產生作品，快速確認封面覆蓋、更新時間與基本分佈。',
      'gallery.snapshot.title': '圖庫摘要',
      'gallery.snapshot.hint': '不用離開圖庫就能先看出封面缺漏、更新新鮮度與內容分佈。',
      'gallery.snapshot.total': '作品數',
      'gallery.snapshot.covers': '封面覆蓋',
      'gallery.snapshot.categories': '類別數',
      'gallery.snapshot.latest': '最近更新',
      'gallery.snapshot.highlights': '重點提示',
      'gallery.snapshot.empty': '載入圖庫後會在這裡顯示封面覆蓋與更新摘要。',
      'gallery.snapshot.latest_none': '尚無圖庫資料。',
      'gallery.snapshot.missing_covers': '缺少封面：{count}',
      'gallery.snapshot.top_category': '主要類別：{name}（{count}）',
      'gallery.snapshot.age_mix': '年齡分佈：{ages}',
    });

    const ui = {
      timer: null,
      logCursor: 0,
      activeLogRunId: null,
      formHydratedRunId: '',
      lastLogReceiptTs: 0,
      apiVersion: '',
      apiCapabilities: {
        queue_api: null,
        alerts_api: null,
        capacity_api: null,
        configs_api: null,
        system_cpu: null,
        system_processes: null,
        system_sampled_at: null,
        system_model_cache: null,
      },
      historyRows: [],
      selectedRunId: '',
      selectedRunBookByRun: {},
      latestStatus: null,
      lastSystemStatus: null,
      lastQueue: null,
      lastAlerts: [],
      lastCapacity: null,
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
      lastModuleJobsData: null,
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
      presetSpeakerSamples: [],
      customSpeakerDirs: [],
      customSpeakerFiles: [],
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
        showAdvanced: false,
        pendingKey: '',
        pendingPromise: null,
        lastFetchKey: '',
        lastFetchAt: 0,
        renderSignature: '',
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

    function looksCorruptedText(value) {
      const text = String(value == null ? '' : value);
      if (!text) return false;
      if (/[\uE000-\uF8FF\uFFFD]/.test(text)) return true;
      if (text.indexOf('嚗') >= 0) return true;
      const questionCount = (text.match(/\?/g) || []).length;
      return questionCount >= 3;
    }

    function t(key, fallback) {
      const lang = ui.language && I18N[ui.language] ? ui.language : 'en';
      const table = I18N[lang] || {};
      if (Object.prototype.hasOwnProperty.call(table, key)) {
        const value = table[key];
        if (!(lang === 'zh-TW' && looksCorruptedText(value))) return value;
      }
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

    function renderEmptyStateMarkup(title, copy, extraClass) {
      const classes = ['empty-state'];
      if (extraClass) classes.push(extraClass);
      return (
        '<div class="' + classes.join(' ') + '">' +
          '<strong class="empty-state-title">' + escapeHtml(String(title || '')) + '</strong>' +
          '<span class="empty-state-copy">' + escapeHtml(String(copy || '')) + '</span>' +
        '</div>'
      );
    }

    function renderGalleryEmptyState() {
      return renderEmptyStateMarkup(
        t('gallery.empty.title', 'No stories to preview yet.'),
        t('gallery.empty.copy', 'Generated covers and story cards will appear here after the first successful run.')
      );
    }

    function renderGallerySnapshot(data) {
      const images = Array.isArray(data && data.images) ? data.images : [];
      let withCover = 0;
      let latestModified = 0;
      const categories = Object.create(null);
      const ages = Object.create(null);

      for (let i = 0; i < images.length; i += 1) {
        const item = images[i] || {};
        if (item.cover) withCover += 1;

        const modified = Number(item.modified || 0);
        if (Number.isFinite(modified) && modified > latestModified) latestModified = modified;

        const category = String(item.category || '').trim();
        if (category && category !== '-') {
          categories[category] = (categories[category] || 0) + 1;
        }

        const age = String(item.age || '').trim();
        if (age && age !== '-') ages[age] = true;
      }

      const categoryNames = Object.keys(categories);
      let topCategory = '';
      let topCategoryCount = 0;
      for (let i = 0; i < categoryNames.length; i += 1) {
        const name = categoryNames[i];
        const count = parseIntSafe(categories[name], 0);
        if (count > topCategoryCount) {
          topCategory = name;
          topCategoryCount = count;
        }
      }
      const ageNames = Object.keys(ages).sort();

      const totalNode = byId('gallery_stat_total');
      const coversNode = byId('gallery_stat_covers');
      const categoriesNode = byId('gallery_stat_categories');
      const latestNode = byId('gallery_stat_latest');
      if (totalNode) totalNode.textContent = String(images.length);
      if (coversNode) coversNode.textContent = String(withCover) + '/' + String(images.length);
      if (categoriesNode) categoriesNode.textContent = String(categoryNames.length);
      if (latestNode) {
        latestNode.textContent = latestModified > 0
          ? new Date(latestModified * 1000).toLocaleString()
          : t('gallery.snapshot.latest_none', 'No gallery data yet.');
      }

      const highlightNode = byId('gallery_highlights');
      if (!highlightNode) return;

      const highlights = [];
      if (!images.length) {
        highlights.push(t('gallery.snapshot.empty', 'Load the gallery to see freshness and cover coverage.'));
      } else {
        const missingCovers = Math.max(0, images.length - withCover);
        if (missingCovers > 0) {
          highlights.push(tf('gallery.snapshot.missing_covers', {count: String(missingCovers)}, 'Missing covers: {count}'));
        }
        if (topCategory) {
          highlights.push(tf('gallery.snapshot.top_category', {name: topCategory, count: String(topCategoryCount)}, 'Top category: {name} ({count})'));
        }
        if (ageNames.length) {
          highlights.push(tf('gallery.snapshot.age_mix', {ages: ageNames.join(' / ')}, 'Age mix: {ages}'));
        }
      }
      if (!highlights.length) {
        highlights.push(t('gallery.snapshot.empty', 'Load the gallery to see freshness and cover coverage.'));
      }

      highlightNode.innerHTML = highlights.map(function (text) {
        return '<div class="list-item advisory-info">' + escapeHtml(String(text)) + '</div>';
      }).join('');
    }

    function renderImageGalleryEmptyState() {
      return renderEmptyStateMarkup(
        t('msg.no_generated_images', 'No generated images yet.'),
        t('msg.select_story_root_for_images', 'Load a story root or wait for image generation to populate this grid.')
      );
    }

    function setEvaluationChartPlaceholder(visible) {
      const emptyNode = byId('eval_chart_empty');
      const canvasNode = byId('evalRadarChart');
      if (emptyNode) emptyNode.style.display = visible ? 'flex' : 'none';
      if (canvasNode) canvasNode.style.display = visible ? 'none' : 'block';
    }

    function renderPageHeader() {
      const tab = String(ui.activeTab || 'overview');
      const titleNode = byId('page_title');
      const subtitleNode = byId('page_subtitle');
      if (titleNode) {
        titleNode.textContent = t('page.' + tab + '.title', t('tab.' + tab, 'Dashboard'));
      }
      if (subtitleNode) {
        subtitleNode.textContent = t('page.' + tab + '.sub', t('hero.sub', 'Operate runs, inspect alerts, manage queue priority, and audit production history from one dashboard.'));
      }
    }

    function applyLanguage() {
      document.documentElement.lang = ui.language;
      document.title = t('title.dashboard', 'GenAI Chief Control Plane');

      const staticMappings = [
        ['hero_eyebrow', 'hero.eyebrow', 'GenAI Operations'],
        ['hero_title', 'hero.title', 'Chief Control Plane'],
        ['label_auto_refresh_text', 'label.auto_refresh', 'Auto refresh'],
        ['label_language', 'label.language', 'Language'],
        ['kpi_label_system_state', 'kpi.system_state', 'Run State'],
        ['kpi_label_queue_depth', 'kpi.queue_depth', 'Queue'],
        ['kpi_label_success_rate', 'kpi.progress', 'Progress'],
        ['kpi_label_avg_duration', 'kpi.elapsed', 'Elapsed'],
        ['kpi_label_gpu_cost', 'kpi.updated', 'Last Update'],
        ['label_tab_gallery', 'label.tab_gallery', 'Gallery'],
        ['label_tab_overview', 'tab.overview', 'Generate'],
        ['label_tab_ops', 'tab.ops', 'Operations'],
        ['label_tab_detail', 'tab.detail', 'Run Detail'],
        ['label_tab_evaluation', 'tab.evaluation', 'Evaluation'],
        ['label_tab_modules', 'tab.modules', 'Modules'],
        ['gallery_title', 'gallery.title', 'Story Gallery'],
        ['gallery_sub', 'gallery.sub', 'Browse generated stories with cover previews and quick metadata.'],
        ['gallery_status_title', 'gallery.snapshot.title', 'Gallery Snapshot'],
        ['gallery_status_hint', 'gallery.snapshot.hint', 'Use this summary to spot freshness gaps and missing covers without leaving the gallery.'],
        ['gallery_label_total', 'gallery.snapshot.total', 'Stories'],
        ['gallery_label_covers', 'gallery.snapshot.covers', 'Covers'],
        ['gallery_label_categories', 'gallery.snapshot.categories', 'Categories'],
        ['gallery_label_latest', 'gallery.snapshot.latest', 'Latest Update'],
        ['gallery_highlights_title', 'gallery.snapshot.highlights', 'Highlights'],
        ['gallery_empty_title', 'gallery.empty.title', 'No stories to preview yet.'],
        ['gallery_empty_copy', 'gallery.empty.copy', 'Generated covers and story cards will appear here after the first successful run.'],
        ['overview_composer_title', 'overview.composer.title', 'Run Composer'],
        ['overview_composer_sub', 'overview.composer.sub', 'Product mode supports queueing with priority and versioned run profiles.'],
        ['demo_storyline_title', 'demo.storyline.title', 'Demo Storyline'],
        ['demo_storyline_sub', 'demo.storyline.sub', 'Use this order for a concise thesis demo: baseline, controlled generation, modular rerun, then evaluation.'],
        ['demo_step_1_title', 'demo.step1.title', 'KG baseline'],
        ['demo_step_1_copy', 'demo.step1.copy', 'Stay in preset mode to show how age, category, theme, and subcategory are filled by KG defaults.'],
        ['demo_step_2_title', 'demo.step2.title', 'Controlled generation'],
        ['demo_step_2_copy', 'demo.step2.copy', 'Switch to custom mode, add prompt and materials, then explain that user intent is normalized under KG constraints.'],
        ['demo_step_3_title', 'demo.step3.title', 'Module proof'],
        ['demo_step_3_copy', 'demo.step3.copy', 'Use Text, Image, Translation, or Voice Studio to rerun only one layer instead of the whole pipeline.'],
        ['demo_step_4_title', 'demo.step4.title', 'Evaluation evidence'],
        ['demo_step_4_copy', 'demo.step4.copy', 'Finish in Evaluation to discuss quality metrics, findings, and how changes affected the final output.'],
        ['demo_storyline_hint', 'demo.storyline.hint', 'Recommended recording flow: preset run, custom rerun, one module-only regeneration, then evaluation summary.'],
        ['kg_summary_title', 'kg.summary.title', 'Generation Logic Snapshot'],
        ['kg_summary_sub', 'kg.summary.sub', 'Summarize how KG defaults, user control, runtime strategy, and saved artifacts will shape the current run.'],
        ['kg_summary_label_mode', 'kg.summary.label.mode', 'Input Mode'],
        ['kg_summary_label_source', 'kg.summary.label.source', 'Control Source'],
        ['kg_summary_label_scope', 'kg.summary.label.scope', 'Story Scope'],
        ['kg_summary_label_plan', 'kg.summary.label.plan', 'Model Plan'],
        ['kg_summary_hint', 'kg.summary.hint', 'Keep the full graph as supporting evidence. In the main dashboard, show only the logic summary that directly affects the generated story.'],
        ['overview_telemetry_title', 'overview.telemetry.title', 'Live Telemetry'],
        ['quick_profile_label', 'overview.quick_profile.label', 'Workflow Preset'],
        ['overview_system_panel_title', 'overview.system.title', 'System Resources'],
        ['overview_process_panel_title', 'overview.process.title', 'Run Context'],
        ['overview_advisory_title', 'overview.advisory.title', 'Run Readiness'],
        ['overview_resource_label_cpu', 'overview.resource.cpu', 'CPU'],
        ['overview_resource_label_ram', 'overview.resource.ram', 'RAM'],
        ['overview_resource_label_gpu', 'overview.resource.gpu', 'GPU'],
        ['overview_resource_label_vram', 'overview.resource.vram', 'VRAM'],
        ['overview_process_label_cpu', 'overview.process.stage', 'Stage'],
        ['overview_process_label_ram', 'overview.process.book', 'Book'],
        ['overview_process_label_threads', 'overview.process.updated', 'Updated'],
        ['overview_process_label_uptime', 'overview.process.uptime', 'Uptime'],
        ['overview_live_logs_title', 'overview.logs.title', 'Live Logs (Now)'],
        ['overview_live_logs_hint', 'overview.logs.hint', 'Latest lines from the active run. Full logs are in Run Detail.'],
        ['ops_queue_title', 'ops.queue.title', 'Queue and Priority'],
        ['ops_summary_title', 'ops.summary.title', 'Operations Snapshot'],
        ['ops_summary_label_active', 'ops.summary.active', 'Active Run'],
        ['ops_summary_label_queue', 'ops.summary.queue', 'Queued Runs'],
        ['ops_summary_label_alerts', 'ops.summary.alerts', 'Open Alerts'],
        ['ops_summary_label_modules', 'ops.summary.modules', 'Module Jobs'],
        ['ops_summary_label_health', 'ops.summary.health', 'Ops Health'],
        ['ops_alert_title', 'ops.alert.title', 'Alert Center'],
        ['ops_alert_hint', 'ops.alert.hint', 'Alerts include queue pressure, repeated failures, and run-stop incidents.'],
        ['ops_capacity_title', 'ops.capacity.title', 'Capacity and Cost'],
        ['cap_label_runs', 'ops.capacity.window_runs', 'Window Runs'],
        ['cap_label_success_rate', 'ops.capacity.success_rate', 'Success Rate'],
        ['cap_label_throughput', 'ops.capacity.books_per_hour', 'Books / Hour'],
        ['cap_label_queue_delay', 'ops.capacity.avg_queue_delay', 'Avg Queue Delay'],
        ['cap_label_gpu_hours', 'ops.capacity.gpu_hours', 'GPU Hours'],
        ['cap_label_gpu_cost', 'ops.capacity.gpu_cost', 'GPU Cost'],
        ['ops_config_title', 'ops.config.title', 'Config Versions'],
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
        ['detail_artifact_label_story_root', 'detail.artifact.story_root', 'Story Root'],
        ['detail_artifact_label_book', 'detail.artifact.book', 'Selected Book'],
        ['detail_artifact_label_stage', 'detail.artifact.stage', 'Last Stage'],
        ['detail_artifact_label_eval', 'detail.artifact.eval', 'Evaluation'],
        ['detail_label_book', 'detail.book', 'Book'],
        ['detail_meta_queue_delay', 'detail.summary.queue_delay', 'Queue Delay'],
        ['detail_meta_started_at', 'detail.summary.started_at', 'Started At'],
        ['detail_meta_finished_at', 'detail.summary.finished_at', 'Finished At'],
        ['detail_timeline_title', 'detail.timeline.title', 'Timeline and Alerts'],
        ['detail_timeline_sub', 'detail.timeline.sub', 'Run-level events and alerts for the whole batch.'],
        ['detail_related_alerts_title', 'detail.related_alerts.title', 'Related Alerts'],
        ['detail_logs_title', 'detail.logs.title', 'Run Logs'],
        ['detail_logs_sub', 'detail.logs.sub', 'Select a book to inspect its captured terminal log.'],
        ['evaluation_title', 'eval.title', 'Evaluation Diagnostics'],
        ['evaluation_sub', 'eval.sub', 'Inspect assessment reports by latest story, run ID, or manual story root.'],
        ['label_evaluation_source', 'eval.source', 'Data Source'],
        ['label_evaluation_run', 'eval.run_id', 'Run ID'],
        ['label_evaluation_book', 'eval.book', 'Book'],
        ['label_evaluation_story_root', 'eval.story_root', 'Story Root'],
        ['label_evaluation_branch', 'eval.branch', 'Branch'],
        ['evaluation_branch_hint', 'eval.branch_hint', 'Use the report variant name. In most cases, keep `canonical`.'],
        ['eval_label_overall', 'eval.overall', 'Overall Score'],
        ['eval_label_scope', 'eval.scope', 'Scope'],
        ['eval_label_branch', 'eval.branch_used', 'Branch'],
        ['eval_label_report_file', 'eval.report_file', 'Report File'],
        ['eval_meta_source_label', 'eval.meta.source', 'Source'],
        ['eval_meta_run_label', 'eval.meta.run_id', 'Run ID'],
        ['eval_meta_book_label', 'eval.book', 'Book'],
        ['eval_meta_story_root_label', 'eval.meta.story_root', 'Story Root'],
        ['eval_insight_title', 'eval.insight.title', 'Evaluation Insights'],
        ['evaluation_chart_title', 'eval.chart.title', 'Dimension Radar'],
        ['eval_chart_empty_title', 'eval.chart.empty.title', 'No evaluation chart yet.'],
        ['eval_chart_empty_copy', 'eval.chart.empty.copy', 'Load a story report to compare dimension scores on the radar chart.'],
        ['evaluation_log_title', 'eval.log.title', 'Assessment JSON'],
        ['module_jobs_title', 'module.jobs.title', 'Module Jobs'],
        ['module_job_detail_title', 'module.job_detail.title', 'Module Job Detail'],
        ['module_job_events_title', 'module.job_events.title', 'Events'],
        ['module_job_logs_title', 'module.job_logs.title', 'Logs'],
        ['module_summary_title', 'module.summary.title', 'Module Snapshot'],
        ['module_summary_label_active', 'module.summary.active', 'Active Job'],
        ['module_summary_label_pending', 'module.summary.pending', 'Pending Jobs'],
        ['module_summary_label_history', 'module.summary.history', 'Visible Records'],
        ['module_summary_label_selected', 'module.summary.selected', 'Selected Job'],
        ['module_demo_sub', 'module.demo.sub', 'Use this area to prove that the system supports local regeneration: change one layer, keep the rest of the pipeline intact.'],
        ['module_demo_story_title', 'module.demo.story.title', '1. Freeze the story draft'],
        ['module_demo_story_copy', 'module.demo.story.copy', 'Run Text Studio first to create the baseline story, then use the resulting story root as the anchor for later comparisons.'],
        ['module_demo_image_title', 'module.demo.image.title', '2. Regenerate one modality only'],
        ['module_demo_image_copy', 'module.demo.image.copy', 'Move to Image, Translation, or Voice Studio and rerun only the weak layer to show controllability without recomputing everything.'],
        ['module_demo_eval_title', 'module.demo.eval.title', '3. Close the loop with evidence'],
        ['module_demo_eval_copy', 'module.demo.eval.copy', 'After a module rerun, open Evaluation or Gallery to compare whether the edited layer actually improved the final artifact.'],
        ['module_workbenches_title', 'module.workbenches.title', 'Module Workbenches'],
        ['module_workbenches_sub', 'module.workbenches.sub', 'Run text, image, translation, and voice independently without executing the full pipeline.'],
        ['module_tab_story', 'module.tab.story', 'Text Studio'],
        ['module_tab_image', 'module.tab.image', 'Image Studio'],
        ['module_tab_translation', 'module.tab.translation', 'Translation Studio'],
        ['module_tab_voice', 'module.tab.voice', 'Voice Studio'],
        ['module_tab_general', 'module.tab.general', 'General Studio'],
        ['studio_story_title', 'module.studio.story.title', 'Text Studio'],
        ['studio_story_sub', 'module.studio.story.sub', 'Generate standalone story drafts and queue text-only runs without touching images or voice.'],
        ['studio_image_title', 'module.studio.image.title', 'Image Studio'],
        ['studio_image_sub', 'module.studio.image.sub', 'Inspect existing image tasks, tweak prompts, and rerun only the visual layer for a story.'],
        ['studio_translation_title', 'module.studio.translation.title', 'Translation Studio'],
        ['studio_translation_sub', 'module.studio.translation.sub', 'Translate existing story outputs, choose target languages, and rerun translation independently.'],
        ['studio_voice_title', 'module.studio.voice.title', 'Voice Studio'],
        ['studio_voice_sub', 'module.studio.voice.sub', 'Generate narration from an existing story root, with direct control over speaker samples and page ranges.'],
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
        ['btn_demo_jump_generate', 'btn.demo_generate', 'Focus Generate'],
        ['btn_demo_jump_modules', 'btn.demo_modules', 'Open Modules'],
        ['btn_demo_jump_evaluation', 'btn.demo_evaluation', 'Open Evaluation'],
        ['btn_start', 'btn.start', 'Start / Queue'],
        ['btn_stop', 'btn.stop', 'Stop Active'],
        ['btn_save_local', 'btn.save_local', 'Save Local'],
        ['btn_load_local', 'btn.load_local', 'Load Local'],
        ['btn_save_version', 'btn.save_version', 'Save Config Version'],
        ['btn_record_start', 'btn.record_start', 'Start Recording'],
        ['btn_record_stop', 'btn.record_stop', 'Stop Recording'],
        ['btn_record_save', 'btn.record_save', 'Save As Speaker WAV'],
        ['btn_overview_clear_view', 'btn.clear_view', 'Clear View'],
        ['btn_clear_history', 'btn.clear_history', 'Clear Ops History'],
        ['btn_detail_refresh', 'btn.refresh_detail', 'Refresh Detail'],
        ['btn_eval_refresh', 'btn.refresh_evaluation', 'Refresh Evaluation'],
        ['btn_modules_refresh', 'btn.refresh_jobs', 'Refresh Jobs'],
        ['btn_module_clear_view', 'btn.clear_module_view', 'Clear View'],
        ['btn_module_show_all', 'btn.show_all', 'Show All'],
        ['btn_module_job_stop', 'btn.stop_selected', 'Stop Selected'],
        ['btn_module_focus_story', 'btn.module_focus_story', 'Text proof'],
        ['btn_module_focus_image', 'btn.module_focus_image', 'Image proof'],
        ['btn_module_focus_eval', 'btn.module_focus_eval', 'Open Evaluation'],
        ['btn_images_refresh', 'btn.refresh_images', 'Refresh Images'],
        ['btn_module_trans_target_recommended', 'btn.recommended', 'Recommended'],
        ['btn_module_trans_target_all', 'btn.select_all', 'Select All'],
        ['btn_module_trans_target_none', 'btn.clear', 'Clear'],
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
        ['#tab_overview label[for="model_plan"]', 'overview.field.model_plan', 'Model Plan'],
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
        overviewStrictTranslation.parentElement.lastChild.textContent = t('overview.toggle.strict_translation', 'Translation required');
      }
      const overviewStrictVoice = document.querySelector('#tab_overview label.chip-check input#strict_voice');
      if (overviewStrictVoice && overviewStrictVoice.parentElement) {
        overviewStrictVoice.parentElement.lastChild.textContent = t('overview.toggle.strict_voice', 'Voice required');
      }

      const presetButtons = document.querySelectorAll('#tab_overview button[data-preset]');
      for (let i = 0; i < presetButtons.length; i += 1) {
        const btn = presetButtons[i];
        const preset = String(btn.getAttribute('data-preset') || '').toLowerCase();
        if (!preset) continue;
        btn.textContent = t('overview.preset.' + preset, btn.textContent);
      }

      setTextById('model_plan_hint', 'overview.model_plan.hint', 'Auto chooses a model profile from the current hardware. Workflow presets also update this field.');
      setTextById('model_plan_scope_hint', 'overview.model_plan.scope_hint', 'Use this only when you want to change model/hardware strategy without changing the rest of the workflow.');
      setTextById('quick_profile_hint', 'overview.quick_profile.hint', 'Workflow presets change model plan plus retries, stage toggles, and required-stage behavior.');
      setTextById('strict_modes_hint', 'overview.strict_modes.hint', 'If required, that stage must succeed or the book is marked failed. Turn it off to allow degraded output.');
      const modelPlanSelect = byId('model_plan');
      if (modelPlanSelect && modelPlanSelect.options) {
        for (let i = 0; i < modelPlanSelect.options.length; i += 1) {
          const option = modelPlanSelect.options[i];
          const value = String(option.value || '').toLowerCase();
          if (!value) continue;
          option.text = t('overview.model_plan.' + value, option.text);
        }
      }
      renderModelPlanStatus(ui.lastSystemStatus);
      renderSystemTelemetry(ui.lastSystemStatus);
      renderKgSummary();
      renderDemoStoryline();
      updateHeaderKpis(ui.latestStatus || {}, ui.lastCapacity || {});
      syncStrictOptionAvailability();

      setTextById('overview_metric_success', 'overview.metric.success', 'Success');
      setTextById('overview_metric_failed', 'overview.metric.failed', 'Failed');
      setTextById('overview_metric_eta', 'overview.metric.eta', 'ETA');
      setTextById('overview_meta_run_id', 'overview.meta.run_id', 'Run ID');
      setTextById('overview_meta_exit_code', 'overview.meta.exit_code', 'Exit Code');
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
        ['voice_script', 'placeholder.voice_script', 'Read 3 to 5 calm, natural sentences with one line of narration, one short line of dialogue, and one clear pause.'],
        ['theme_custom', 'placeholder.theme_custom', 'ex: friendship, courage, mystery'],
        ['subcategory_custom', 'placeholder.subcategory_custom', 'ex: forest, tradition, science'],
        ['speaker_dir', 'placeholder.speaker_dir', 'ex: models/XTTS-v2/samples/custom'],
        ['evaluation_branch', 'placeholder.evaluation_branch', 'canonical'],
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

      if (imageGallery && (!ui.imageItems || ui.imageItems.length === 0)) {
        imageGallery.innerHTML = renderImageGalleryEmptyState();
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

      syncEvaluationAdvancedControls();
      renderPageHeader();
    }

    function byId(id) {
      return document.getElementById(id);
    }

    function modelPlanLabel(value) {
      const key = String(value || '').trim().toLowerCase();
      if (!key) return t('overview.model_plan.unknown', 'Unknown');
      return t('overview.model_plan.' + key, key);
    }

    function formatGiBFromBytes(value) {
      const bytes = Number(value || 0);
      if (!Number.isFinite(bytes) || bytes <= 0) return '0.0';
      return (bytes / (1024 * 1024 * 1024)).toFixed(1);
    }

    function formatSampledTime(isoText) {
      if (!isoText) return '-';
      const d = new Date(isoText);
      if (Number.isNaN(d.getTime())) return '-';
      return d.toLocaleTimeString();
    }

    function localizeBackendMessage(message) {
      const text = String(message || '');
      if (!text || ui.language !== 'zh-TW') return text;
      const exactMap = {
        'No assessment report found for selected story.': '找不到所選故事的評估報告。',
        'No stories found.': '目前找不到可用的故事。',
        'run_id is required when source=run.': '當資料來源是 Run ID 時，必須先選擇 run_id。',
        'story_root is required when source=story_root.': '當資料來源是故事路徑時，必須先輸入 story_root。',
        'No evaluation story root resolved.': '目前無法解析評估用的故事路徑。',
      };
      if (Object.prototype.hasOwnProperty.call(exactMap, text)) {
        return exactMap[text];
      }
      if (text.indexOf('Invalid story_root:') === 0) {
        return '無效的 story_root：' + text.slice('Invalid story_root:'.length).trim();
      }
      if (text.indexOf('Unable to resolve story_root for run_id:') === 0) {
        return '無法從這個 run_id 解析 story_root：' + text.slice('Unable to resolve story_root for run_id:'.length).trim();
      }
      if (text.indexOf('Failed to parse assessment report:') === 0) {
        return '評估報告解析失敗：' + text.slice('Failed to parse assessment report:'.length).trim();
      }
      return text;
    }

    function setPillTone(node, tone, text) {
      if (!node) return;
      node.className = 'pill';
      const value = String(tone || '').trim().toLowerCase();
      if (value) node.classList.add(value);
      if (text != null) node.textContent = String(text);
    }

    function advisoryRank(level) {
      const value = String(level || '').trim().toLowerCase();
      if (value === 'critical') return 3;
      if (value === 'warning') return 2;
      return 1;
    }

    function formatPillLabel(value) {
      const text = String(value || '').trim();
      if (!text) return '-';
      return text.charAt(0).toUpperCase() + text.slice(1);
    }

    function healthLabel(value) {
      const key = String(value || '').trim().toLowerCase();
      return t('health.level.' + key, formatPillLabel(key));
    }

    function summarizeModelCache(entries) {
      if (!Array.isArray(entries) || !entries.length) return t('health.model_cache.empty', 'Model cache: empty');
      const parts = [];
      for (let i = 0; i < entries.length; i += 1) {
        const item = entries[i] || {};
        const kind = String(item.kind || 'model');
        const inUse = parseIntSafe(item.in_use, 0);
        const offloaded = Boolean(item.offloaded);
        let state = t('health.model_cache.state.ready', 'ready');
        if (inUse > 0) state = t('health.model_cache.state.busy', 'busy');
        else if (offloaded) state = t('health.model_cache.state.offloaded', 'offloaded');
        parts.push(kind + ' ' + state);
      }
      return tf('health.model_cache.summary', {items: parts.join(' | ')}, 'Model cache: {items}');
    }

    function buildChiefProcessFallback(systemPayload, statusPayload) {
      const system = systemPayload || {};
      const status = statusPayload || ui.latestStatus || {};
      const processes = system && system.processes ? system.processes : {};
      const chief = processes && processes.chief ? processes.chief : null;
      if (chief) return chief;
      if (!status || !status.running) return null;
      const pid = parseIntSafe(status.pid, 0);
      if (pid <= 0) return null;
      return {
        pid: pid,
        label: 'chief',
        name: 'chief',
        status: 'running',
        cpu_percent: null,
        rss: null,
        threads: null,
        uptime_sec: Number(status.elapsed_sec || 0),
        limited: true,
      };
    }

    function heartbeatThresholdsForStage(stageText) {
      const stage = String(stageText || '').trim().toUpperCase();
      if (!stage) return {warningSec: 300, criticalSec: 600};
      if (stage.indexOf('STORY:') === 0) return {warningSec: 600, criticalSec: 1200};
      if (stage.indexOf('PRE_EVAL:') === 0) return {warningSec: 420, criticalSec: 900};
      if (stage.indexOf('IMAGE:') === 0) return {warningSec: 420, criticalSec: 900};
      if (stage.indexOf('VOICE:') === 0 || stage.indexOf('TRANSLATION:') === 0) return {warningSec: 300, criticalSec: 720};
      return {warningSec: 300, criticalSec: 600};
    }

    function isTerminalRunState(state) {
      const normalized = String(state || '').trim().toLowerCase();
      return normalized === 'completed' || normalized === 'failed' || normalized === 'error' || normalized === 'stopped';
    }

    function latestRunIdFromStatus(statusPayload) {
      const status = statusPayload || {};
      const candidate = status.latest_run_id != null
        ? status.latest_run_id
        : (!status.running ? status.run_id : '');
      return String(candidate || '').trim();
    }

    function latestRunStateFromStatus(statusPayload, fallbackState) {
      const status = statusPayload || {};
      const candidate = status.latest_run_state != null ? status.latest_run_state : fallbackState;
      return String(candidate || '').trim().toLowerCase() || 'idle';
    }

    function renderProcessTelemetry(data) {
      const payload = data || ui.lastSystemStatus || {};
      const processes = payload && payload.processes ? payload.processes : {};
      const chief = buildChiefProcessFallback(payload, ui.latestStatus);
      const dashboardProc = processes && processes.dashboard ? processes.dashboard : null;
      const status = ui.latestStatus || {};
      const runner = status && status.runner ? status.runner : {};
      const state = String(runner.state || (status.running ? 'running' : 'idle')).trim().toLowerCase() || 'idle';
      const latestRunId = latestRunIdFromStatus(status);
      const latestState = latestRunStateFromStatus(status, state);
      const currentStage = String(runner.current_stage || '').trim();
      const displayStage = Boolean(status.running)
        ? currentStage
        : String(status.latest_run_stage || currentStage || '').trim();
      const totalBooks = Boolean(status.running)
        ? parseIntSafe(runner.total_books, 0)
        : parseIntSafe(status.latest_run_total_books, parseIntSafe(runner.total_books, 0));
      const currentBook = runner.current_book == null ? null : String(runner.current_book);
      const updatedAgoSource = Boolean(status.running)
        ? status.updated_ago_sec
        : (status.latest_run_updated_ago_sec != null ? status.latest_run_updated_ago_sec : status.updated_ago_sec);
      const updatedAgo = updatedAgoSource == null ? '-' : (String(Math.round(Number(updatedAgoSource || 0))) + 's');
      const elapsedSource = Boolean(status.running)
        ? status.elapsed_sec
        : (status.latest_run_elapsed_sec != null ? status.latest_run_elapsed_sec : status.elapsed_sec);
      const uptimeText = chief
        ? formatDuration(Number(chief.uptime_sec || 0))
        : (elapsedSource != null ? formatDuration(Number(elapsedSource || 0)) : '-');
      const cpuNode = byId('overview_process_cpu');
      const ramNode = byId('overview_process_ram');
      const threadsNode = byId('overview_process_threads');
      const uptimeNode = byId('overview_process_uptime');
      const detailNode = byId('overview_process_detail');
      const stateNode = byId('overview_process_state');
      const cpuLabelNode = byId('overview_process_label_cpu');
      const ramLabelNode = byId('overview_process_label_ram');
      const threadsLabelNode = byId('overview_process_label_threads');
      const uptimeLabelNode = byId('overview_process_label_uptime');

      if (cpuLabelNode) cpuLabelNode.textContent = t('overview.process.stage', 'Stage');
      if (ramLabelNode) ramLabelNode.textContent = t('overview.process.book', 'Book');
      if (threadsLabelNode) threadsLabelNode.textContent = t('overview.process.updated', 'Updated');
      if (uptimeLabelNode) uptimeLabelNode.textContent = t('overview.process.uptime', 'Uptime');

      if (cpuNode) {
        cpuNode.textContent = displayStage || localizeState(Boolean(status.running) ? state : latestState);
      }
      if (ramNode) {
        if (Boolean(status.running)) {
          ramNode.textContent = currentBook == null ? '-' : currentBook;
        } else {
          ramNode.textContent = totalBooks > 0 ? String(totalBooks) : '-';
        }
      }
      if (threadsNode) threadsNode.textContent = updatedAgo;
      if (uptimeNode) uptimeNode.textContent = uptimeText;

      if (stateNode) {
        if (Boolean(status.running) || chief) {
          setPillTone(stateNode, 'running', t('health.process.active', 'chief active'));
        } else if (latestRunId || isTerminalRunState(latestState)) {
          setPillTone(stateNode, latestState, localizeState(latestState));
        } else {
          setPillTone(stateNode, 'info', t('health.process.idle', 'idle'));
        }
      }

      if (detailNode) {
        if (chief) {
          if (!chief.limited && (chief.cpu_percent != null || chief.rss != null)) {
            detailNode.textContent = tf(
              'health.process.detail.chief_resources',
              {
                pid: String(chief.pid || '-'),
                cpu: chief.cpu_percent != null ? String(Number(chief.cpu_percent || 0).toFixed(1)) : '-',
                ram: chief.rss != null ? formatGiBFromBytes(chief.rss) : '-',
                cache: summarizeModelCache(payload.model_cache || []),
              },
              'PID {pid} | CPU {cpu}% | RAM {ram} GB | {cache}'
            );
          } else {
            detailNode.textContent = tf(
              'health.process.detail.chief_limited',
              {
                pid: String(chief.pid || '-'),
                name: String(chief.name || 'chief'),
                cache: summarizeModelCache(payload.model_cache || []),
              },
              'PID {pid} | {name} | stage-focused telemetry | {cache}'
            );
          }
        } else if (dashboardProc) {
          detailNode.textContent = tf(
            'health.process.detail.dashboard',
            {
              pid: String(dashboardProc.pid || '-'),
              cache: summarizeModelCache(payload.model_cache || []),
            },
            'Dashboard PID {pid} | {cache}'
          );
        } else {
          detailNode.textContent = t('health.process.none', 'No active run process.');
        }
      }
    }

    function buildHealthSnapshot(systemPayload, statusPayload) {
      const system = systemPayload || {};
      const status = statusPayload || {};
      const cpu = system && system.cpu ? system.cpu : {};
      const ram = system && system.ram ? system.ram : {};
      const gpus = Array.isArray(system && system.gpus) ? system.gpus : [];
      const primaryGpu = gpus.length ? (gpus[0] || {}) : null;
      const chief = buildChiefProcessFallback(system, status);
      const modelPlanPayload = system && system.model_plan ? system.model_plan : {};
      const recommendedPlan = String(modelPlanPayload.recommended_plan || '').trim().toLowerCase() || 'balanced';
      const selectedPlan = byId('model_plan') ? String(byId('model_plan').value || 'auto').trim().toLowerCase() : 'auto';
      const advisories = [];

      function push(level, title, detail) {
        advisories.push({level: level, title: title, detail: detail});
      }

      const cpuPercent = Number(cpu.percent || 0);
      const ramPercent = Number(ram.percent || 0);
      const vramPercent = primaryGpu ? Number(primaryGpu.vram_percent || 0) : 0;
      const queueDepth = parseIntSafe(status.queue_depth, 0);
      const updatedAgo = Number(status.updated_ago_sec || 0);
      const running = Boolean(status.running);
      const runner = status && status.runner ? status.runner : {};
      const stageText = String(runner.current_stage || '');
      const heartbeatThresholds = heartbeatThresholdsForStage(stageText);
      const recentLogAgeSec = ui.lastLogReceiptTs > 0 ? ((Date.now() - ui.lastLogReceiptTs) / 1000) : Number.POSITIVE_INFINITY;
      const hasRecentLogs = running && recentLogAgeSec <= 90;

      const hasTelemetry = Boolean(
        system.sampled_at ||
        system.cpu ||
        system.ram ||
        (Array.isArray(system.gpus) && system.gpus.length) ||
        (system.processes && Object.keys(system.processes).length)
      );

      if (!hasTelemetry) {
        push('warning', t('health.advisory.telemetry_missing.title', 'System telemetry missing'), t('health.advisory.telemetry_missing.detail', 'Resource usage is not available yet.'));
      }
      if (vramPercent >= 92 || ramPercent >= 92) {
        push('critical', t('health.advisory.memory_high.title', 'Memory pressure is high'), t('health.advisory.memory_high.detail', 'VRAM or RAM is above 92%. Consider portable mode or pausing heavy stages.'));
      } else if (cpuPercent >= 90 || ramPercent >= 85 || vramPercent >= 85) {
        push('warning', t('health.advisory.memory_warn.title', 'Resource pressure is elevated'), t('health.advisory.memory_warn.detail', 'Current workload is close to system limits.'));
      }
      if (running && !hasRecentLogs && updatedAgo >= heartbeatThresholds.criticalSec) {
        push('critical', t('health.advisory.heartbeat_stale.title', 'Run heartbeat is stale'), tf('health.advisory.heartbeat_stale.detail', {seconds: String(Math.round(updatedAgo))}, 'Status file has not refreshed for {seconds}s.'));
      } else if (running && !hasRecentLogs && updatedAgo >= heartbeatThresholds.warningSec) {
        push('warning', t('health.advisory.heartbeat_slow.title', 'Run heartbeat is slowing down'), t('health.advisory.heartbeat_slow.detail', 'Status updates are slower than expected.'));
      }
      if (running && !chief) {
        push('warning', t('health.advisory.chief_missing.title', 'Chief process not detected'), t('health.advisory.chief_missing.detail', 'The dashboard reports an active run but the chief process is not visible.'));
      }
      if (queueDepth >= 4) {
        push('warning', t('health.advisory.queue_pressure.title', 'Queue depth is growing'), t('health.advisory.queue_pressure.detail', 'Queued jobs may need priority tuning or lower-cost presets.'));
      }
      if (!primaryGpu && (byId('photo_enabled') && byId('photo_enabled').checked)) {
        push('info', t('health.advisory.gpu_missing.title', 'GPU not detected'), t('health.advisory.gpu_missing.detail', 'Image stages will run slower on CPU-only hardware.'));
      }
      if (selectedPlan !== 'auto' && selectedPlan !== recommendedPlan) {
        push(
          'info',
          t('health.advisory.plan_override.title', 'Selected plan overrides hardware recommendation'),
          tf(
            'health.advisory.plan_override.detail',
            {selected: modelPlanLabel(selectedPlan), recommended: modelPlanLabel(recommendedPlan)},
            'Current selection is {selected}, auto recommends {recommended}.'
          )
        );
      }

      advisories.sort(function (a, b) {
        return advisoryRank(b.level) - advisoryRank(a.level);
      });

      let level = 'stable';
      if (advisories.length) level = advisories[0].level;

      let summary = t('health.summary.ready', 'System is ready for the next run.');
      if (running && chief && level === 'stable') {
        summary = t('health.summary.running_healthy', 'Run is active and resource headroom looks healthy.');
      } else if (level === 'critical') {
        summary = advisories[0].title;
      } else if (level === 'warning') {
        summary = advisories[0].title;
      } else if (advisories.length) {
        summary = advisories[0].title;
      }

      const runContext = running
        ? tf('health.run_context.active', {run_id: String(status.run_id || '-'), stage: String(runner.current_stage || 'running')}, 'Run {run_id} | {stage}')
        : t('health.run_context.idle', 'No active run');
      const pressureValue = Math.max(cpuPercent, ramPercent, vramPercent || 0);
      let pressureLabel = t('health.pressure.low', 'low');
      if (pressureValue >= 90) pressureLabel = t('health.pressure.critical', 'critical');
      else if (pressureValue >= 75) pressureLabel = t('health.pressure.elevated', 'elevated');
      else if (pressureValue >= 50) pressureLabel = t('health.pressure.moderate', 'moderate');

      return {
        level: level,
        summary: summary,
        context: runContext,
        pressure: pressureLabel + ' (' + pressureValue.toFixed(1) + '%)',
        advisories: advisories.slice(0, 4),
        recommendedPlan: recommendedPlan,
        selectedPlan: selectedPlan,
      };
    }

    function renderDashboardHealth(systemPayload, statusPayload) {
      const health = buildHealthSnapshot(systemPayload || ui.lastSystemStatus, statusPayload || ui.latestStatus);
      const globalLevel = byId('global_health_level');
      const overviewLevel = byId('overview_health_level');
      setPillTone(globalLevel, health.level, healthLabel(health.level));
      setPillTone(overviewLevel, health.level, healthLabel(health.level));

      const globalSummary = byId('global_health_summary');
      if (globalSummary) globalSummary.textContent = health.summary;
      const globalContext = byId('global_health_context');
      if (globalContext) globalContext.textContent = health.context;
      const overviewSummary = byId('overview_health_summary');
      if (overviewSummary) overviewSummary.textContent = health.summary;

      const advisoryPanel = byId('overview_advisory_panel');
      if (advisoryPanel) advisoryPanel.hidden = !health.advisories.length;
      const advisoryTitle = byId('overview_advisory_title');
      if (advisoryTitle) {
        advisoryTitle.textContent = health.advisories.length
          ? t('overview.advisory.issues', 'Current Issues')
          : t('overview.advisory.title', 'Run Readiness');
      }

      const globalPlan = byId('global_health_plan');
      if (globalPlan) {
        globalPlan.textContent = tf(
          'health.meta.plan',
          {selected: modelPlanLabel(health.selectedPlan), recommended: modelPlanLabel(health.recommendedPlan)},
          'Plan: {selected} | Auto: {recommended}'
        );
      }
      const globalRun = byId('global_health_run');
      if (globalRun) {
        const status = statusPayload || ui.latestStatus || {};
        const runner = status && status.runner ? status.runner : {};
        globalRun.textContent = Boolean(status.running)
          ? tf(
              'health.meta.run',
              {
                text: String(status.run_id || '-') + ' | ' + String(runner.current_book == null ? '-' : runner.current_book),
              },
              'Run: {text}'
            )
          : tf('health.meta.run', {text: t('state.idle', 'idle')}, 'Run: {text}');
      }
      const globalPressure = byId('global_health_pressure');
      if (globalPressure) {
        globalPressure.textContent = tf('health.meta.pressure', {value: health.pressure}, 'Pressure: {value}');
      }

      const advisoryList = byId('overview_advisory_list');
      if (advisoryList) {
        if (!health.advisories.length) {
          advisoryList.innerHTML = '<div class="list-item advisory-info">' + escapeHtml(t('health.advisory.ready', 'System ready. Current settings match the available headroom.')) + '</div>';
        } else {
          advisoryList.innerHTML = health.advisories.map(function (item) {
            const detail = item.detail ? ('<div class="meta">' + escapeHtml(String(item.detail)) + '</div>') : '';
            return '<div class="list-item advisory-' + escapeHtml(String(item.level || 'info')) + '">' +
              '<strong>' + escapeHtml(String(item.title || 'Advisory')) + '</strong>' +
              detail +
              '</div>';
          }).join('');
        }
      }

      return health;
    }

    function formatUpdatedAgo(seconds) {
      if (seconds == null || !Number.isFinite(Number(seconds))) return '-';
      return String(Math.round(Number(seconds))) + 's';
    }

    function formatRunMoment(isoText, compact) {
      if (!isoText) return '-';
      const d = new Date(isoText);
      if (Number.isNaN(d.getTime())) return '-';
      return compact ? d.toLocaleTimeString() : d.toLocaleString();
    }

    function summarizeRunIssue(errorText, stageText) {
      const raw = String(errorText || '').trim();
      const stage = String(stageText || '').trim();
      const source = (raw + ' ' + stage).toLowerCase();
      if (source.indexOf('translation') >= 0) return 'Translation failed';
      if (source.indexOf('voice') >= 0 || source.indexOf('tts') >= 0) return 'Voice generation failed';
      if (source.indexOf('image') >= 0 || source.indexOf('photo') >= 0) return 'Image generation failed';
      if (source.indexOf('pre_eval') >= 0) return 'Pre-evaluation failed';
      if (source.indexOf('eval') >= 0) return 'Final evaluation failed';
      if (source.indexOf('story') >= 0) return 'Story generation failed';
      if (raw) {
        return raw
          .replace(/^errors=/i, '')
          .replace(/[_|]+/g, ' ')
          .replace(/\s+/g, ' ')
          .trim();
      }
      if (stage && stage !== '-') return stage + ' failed';
      return '';
    }

    function suggestedFailureAction(errorText, stageText) {
      const source = (String(errorText || '') + ' ' + String(stageText || '')).toLowerCase();
      if (source.indexOf('translation') >= 0) {
        return 'Check the translation setup or backend first, then rerun.';
      }
      if (source.indexOf('voice') >= 0 || source.indexOf('tts') >= 0) {
        return 'Review voice sample selection and TTS settings before rerunning.';
      }
      if (source.indexOf('image') >= 0 || source.indexOf('photo') >= 0) {
        return 'Review image prompts or model settings before rerunning.';
      }
      if (source.indexOf('pre_eval') >= 0 || source.indexOf('eval') >= 0) {
        return 'Open Evaluation and review the failing report before rerunning.';
      }
      return 'Open Run Detail, inspect the failed book log, then rerun.';
    }

    function deriveOverviewMonitorMode(statusPayload) {
      const status = statusPayload || {};
      const runner = status && status.runner ? status.runner : {};
      const state = String(runner.state || (status.running ? 'running' : 'idle')).trim().toLowerCase();
      const latestState = latestRunStateFromStatus(status, state);
      const latestRunId = latestRunIdFromStatus(status);
      if (Boolean(status.running)) return 'running';
      if (parseIntSafe(status.queue_depth, 0) > 0) return 'idle';
      if (latestRunId || isTerminalRunState(latestState)) {
        return 'postrun';
      }
      return 'idle';
    }

    function renderOverviewMonitor(statusPayload, healthPayload) {
      const status = statusPayload || ui.latestStatus || {};
      const health = healthPayload || buildHealthSnapshot(ui.lastSystemStatus, status);
      const runner = status && status.runner ? status.runner : {};
      const state = String(runner.state || (status.running ? 'running' : 'idle')).trim().toLowerCase() || 'idle';
      const mode = deriveOverviewMonitorMode(status);
      const latestState = latestRunStateFromStatus(status, state);
      const latestRunId = latestRunIdFromStatus(status);
      const card = byId('overview_monitor_card');
      if (card) {
        card.classList.remove('mode-running', 'mode-idle', 'mode-postrun');
        card.classList.add('mode-' + mode);
      }

      const total = mode === 'postrun'
        ? parseIntSafe(status.latest_run_total_books, parseIntSafe(runner.total_books, 0))
        : parseIntSafe(runner.total_books, 0);
      const completed = mode === 'postrun'
        ? parseIntSafe(status.latest_run_completed_books, parseIntSafe(runner.completed_books, 0))
        : parseIntSafe(runner.completed_books, 0);
      const success = mode === 'postrun'
        ? parseIntSafe(status.latest_run_success_books, parseIntSafe(runner.success_books, 0))
        : parseIntSafe(runner.success_books, 0);
      const failed = mode === 'postrun'
        ? parseIntSafe(status.latest_run_failed_books, parseIntSafe(runner.failed_books, 0))
        : parseIntSafe(runner.failed_books, 0);
      const remaining = Math.max(0, total - completed);
      const progress = mode === 'running' && Number.isFinite(Number(status.progress_pct))
        ? Math.max(0, Math.min(100, Number(status.progress_pct)))
        : (total > 0 ? Math.max(0, Math.min(100, (completed / total) * 100)) : 0);
      const updatedAgoText = formatUpdatedAgo(
        mode === 'postrun' && status.latest_run_updated_ago_sec != null
          ? status.latest_run_updated_ago_sec
          : status.updated_ago_sec
      );
      const latestFinishedAtText = formatRunMoment(
        mode === 'postrun'
          ? (status.latest_run_finished_at || status.latest_run_started_at)
          : null,
        true
      );
      const currentStage = String((mode === 'postrun' ? (status.latest_run_stage || runner.current_stage) : runner.current_stage) || '-');
      const latestRunError = String(
        mode === 'postrun'
          ? (status.latest_run_last_error || status.last_error || '')
          : (runner.last_error || status.last_error || '')
      ).trim();
      const latestRunIssue = summarizeRunIssue(latestRunError, currentStage);
      const runId = String(mode === 'running' ? (status.run_id || '-') : (latestRunId || '-'));
      const stateLabel = localizeState(mode === 'running' ? state : latestState);
      const elapsedDisplaySec = mode === 'postrun'
        ? (status.latest_run_elapsed_sec != null ? status.latest_run_elapsed_sec : status.elapsed_sec)
        : status.elapsed_sec;
      const exitCodeDisplay = mode === 'postrun' && status.latest_run_exit_code != null
        ? status.latest_run_exit_code
        : status.exit_code;

      const liveSection = byId('overview_monitor_live');
      const idleSection = byId('overview_monitor_idle');
      if (liveSection) liveSection.hidden = mode !== 'running';
      if (idleSection) idleSection.hidden = mode === 'running';

      const titleNode = byId('overview_monitor_summary_title');
      const copyNode = byId('overview_monitor_summary_copy');
      const primaryLabelNode = byId('overview_monitor_side_label_primary');
      const primaryValueNode = byId('overview_monitor_side_primary');
      const secondaryLabelNode = byId('overview_monitor_side_label_secondary');
      const secondaryValueNode = byId('overview_monitor_side_secondary');

      let summaryTitle = t('overview.monitor.summary.ready', 'Ready for the next run');
      let summaryCopy = t('overview.monitor.copy.ready', 'Adjust the composer on the left, then start or queue a run.');
      let primaryLabel = t('overview.monitor.side.queue', 'Queue');
      let primaryValue = String(parseIntSafe(status.queue_depth, 0));
      let secondaryLabel = t('overview.field.model_plan', 'Model Plan');
      let secondaryValue = modelPlanLabel(health && health.selectedPlan ? health.selectedPlan : 'auto');

      if (mode === 'running') {
        summaryTitle = t('overview.monitor.summary.running', 'Run in progress');
        summaryCopy = t(
          'overview.monitor.copy.running_compact',
          'Review the active book, stage, and pre-evaluation below.'
        );
        primaryLabel = t('overview.meta.run_id', 'Run ID');
        primaryValue = runId;
        secondaryLabel = t('overview.metric.eta', 'ETA');
        secondaryValue = formatDuration(status.eta_sec);
      } else if (parseIntSafe(status.queue_depth, 0) > 0 && mode === 'idle') {
        summaryTitle = t('overview.monitor.summary.queued', 'Queue pending');
        summaryCopy = tf(
          'overview.monitor.copy.queued',
          {count: String(parseIntSafe(status.queue_depth, 0))},
          'No active run right now. {count} job(s) remain in queue.'
        );
        primaryLabel = t('overview.monitor.side.queue', 'Queue');
        primaryValue = String(parseIntSafe(status.queue_depth, 0));
        secondaryLabel = t('overview.field.model_plan', 'Model Plan');
        secondaryValue = modelPlanLabel(health && health.selectedPlan ? health.selectedPlan : 'auto');
      } else if (mode === 'postrun') {
        summaryTitle = tf(
          'overview.monitor.summary.postrun',
          {state: stateLabel},
          'Last run {state}'
        );
        summaryCopy = latestState === 'failed' || latestState === 'error' || latestState === 'stopped'
          ? suggestedFailureAction(latestRunError, currentStage)
          : t(
              'overview.monitor.copy.postrun_compact',
              'Review the latest run summary below before starting again.'
            );
        primaryLabel = t('overview.meta.run_id', 'Run ID');
        primaryValue = runId;
        secondaryLabel = t('detail.summary.finished_at', 'Finished At');
        secondaryValue = latestFinishedAtText !== '-' ? latestFinishedAtText : updatedAgoText;
      }

      if (titleNode) titleNode.textContent = summaryTitle;
      if (copyNode) copyNode.textContent = summaryCopy;
      if (primaryLabelNode) primaryLabelNode.textContent = primaryLabel;
      if (primaryValueNode) primaryValueNode.textContent = primaryValue;
      if (secondaryLabelNode) secondaryLabelNode.textContent = secondaryLabel;
      if (secondaryValueNode) secondaryValueNode.textContent = secondaryValue;

      const lastRunTitleNode = byId('overview_last_run_title');
      const nextStepTitleNode = byId('overview_next_step_title');
      const lastRunIdLabelNode = byId('overview_last_run_label_id');
      const lastRunResultLabelNode = byId('overview_last_run_label_result');
      const lastRunBooksLabelNode = byId('overview_last_run_label_books');
      const lastRunElapsedLabelNode = byId('overview_last_run_label_elapsed');
      if (lastRunTitleNode) lastRunTitleNode.textContent = t('overview.monitor.last_run.title', 'Latest Run');
      if (nextStepTitleNode) nextStepTitleNode.textContent = t('overview.monitor.next.title', 'Next Step');
      if (lastRunIdLabelNode) lastRunIdLabelNode.textContent = t('overview.meta.run_id', 'Run ID');
      if (lastRunResultLabelNode) lastRunResultLabelNode.textContent = t('overview.monitor.last_run.result', 'Result');
      if (lastRunBooksLabelNode) lastRunBooksLabelNode.textContent = t('overview.monitor.last_run.books', 'Books');
      if (lastRunElapsedLabelNode) lastRunElapsedLabelNode.textContent = t('overview.metric.elapsed', 'Elapsed');

      const hasRecentRun = mode === 'postrun' || Boolean(latestRunId) || total > 0 || Number(elapsedDisplaySec || 0) > 0;
      const lastRunStateNode = byId('overview_last_run_state');
      if (lastRunStateNode) {
        setPillTone(
          lastRunStateNode,
          hasRecentRun ? (mode === 'running' ? state : latestState) : 'info',
          hasRecentRun ? stateLabel : t('overview.monitor.result.ready', 'Ready')
        );
      }
      const lastRunIdNode = byId('overview_last_run_id');
      const lastRunResultNode = byId('overview_last_run_result');
      const lastRunBooksNode = byId('overview_last_run_books');
      const lastRunElapsedNode = byId('overview_last_run_elapsed');
      const lastRunHintNode = byId('overview_last_run_hint');
      if (lastRunIdNode) lastRunIdNode.textContent = hasRecentRun ? runId : '-';
      if (lastRunResultNode) lastRunResultNode.textContent = hasRecentRun ? stateLabel : t('overview.monitor.result.ready', 'Ready');
      if (lastRunBooksNode) {
        lastRunBooksNode.textContent = total > 0
          ? (String(completed) + '/' + String(total))
          : '-';
      }
      if (lastRunElapsedNode) lastRunElapsedNode.textContent = hasRecentRun ? formatDuration(elapsedDisplaySec) : '-';
      if (lastRunHintNode) {
        if (!hasRecentRun) {
          lastRunHintNode.textContent = t('overview.monitor.last_run.none', 'No recent run summary yet.');
        } else {
          const hintParts = [];
          if (latestRunIssue) {
            hintParts.push('Issue ' + latestRunIssue);
          }
          if (exitCodeDisplay != null) {
            hintParts.push(t('overview.meta.exit_code', 'Exit Code') + ' ' + String(exitCodeDisplay));
          }
          if (currentStage && currentStage !== '-' && String(currentStage).trim().toLowerCase() !== 'done') {
            hintParts.push(t('overview.process.stage', 'Stage') + ' ' + currentStage);
          }
          if (failed > 0) {
            hintParts.push(t('overview.metric.failed', 'Failed') + ' ' + String(failed));
          }
          if (!hintParts.length && latestFinishedAtText !== '-') {
            hintParts.push(t('detail.summary.finished_at', 'Finished At') + ' ' + formatRunMoment(status.latest_run_finished_at || status.latest_run_started_at, false));
          }
          lastRunHintNode.textContent = hintParts.length ? hintParts.join(' | ') : t('overview.monitor.last_run.none', 'No recent run summary yet.');
        }
      }

      const nextSummaryNode = byId('overview_next_step_summary');
      const hasPlanOverride = Boolean(
        health &&
        health.selectedPlan &&
        health.recommendedPlan &&
        String(health.selectedPlan) !== String(health.recommendedPlan)
      );
      const nextItems = [];
      let nextSummary = t('overview.monitor.next.ready', 'Configure the next run from the composer on the left.');

      if (parseIntSafe(status.queue_depth, 0) > 0 && mode !== 'running') {
        nextSummary = 'Queued jobs are waiting. Open Ops if you need to reprioritize or cancel them.';
        nextItems.push('Open Ops to reprioritize or cancel queued jobs.');
        if (parseIntSafe(status.queue_depth, 0) > 1) {
          nextItems.push('Queued jobs: ' + String(parseIntSafe(status.queue_depth, 0)));
        }
      } else if (mode === 'postrun') {
        if (latestState === 'failed' || latestState === 'error' || latestState === 'stopped') {
          nextSummary = suggestedFailureAction(latestRunError, currentStage);
          if (failed > 0 && total > 0) {
            nextItems.push('Failed books: ' + String(failed) + '/' + String(total));
          }
          if (latestRunIssue) {
            nextItems.push('Last issue: ' + latestRunIssue);
          }
          nextItems.push('Open Run Detail and select the failed book to inspect its log.');
        } else {
          nextSummary = 'Review the generated outputs, then start the next batch.';
          nextItems.push('Open Gallery to spot-check images and covers.');
          nextItems.push('Open Evaluation to review the latest score.');
        }
      } else {
        nextSummary = 'Set story scope and voice on the left, then start a new run.';
        nextItems.push('Choose the book count and story preset.');
        nextItems.push('If using a custom voice, select it from the voice panel first.');
      }

      if (hasPlanOverride) {
        nextItems.push(
          'Plan override: ' +
          modelPlanLabel(health.selectedPlan) +
          ' | Auto recommends ' +
          modelPlanLabel(health.recommendedPlan)
        );
      }

      if (nextSummaryNode) {
        nextSummaryNode.textContent = nextSummary;
      }

      const nextListNode = byId('overview_next_step_list');
      if (nextListNode) {
        nextListNode.hidden = !nextItems.length;
        nextListNode.innerHTML = nextItems.map(function (text) {
          return '<div class="list-item advisory-info">' + escapeHtml(String(text)) + '</div>';
        }).join('');
      }
    }

    function renderModelPlanStatus(data) {
      const selectedValue = byId('model_plan') ? (byId('model_plan').value || 'auto') : 'auto';
      const payload = data && data.model_plan ? data.model_plan : {};
      const hardware = payload.hardware || {};
      const acceleratorRaw = String(hardware.accelerator || '').trim();
      const accelerator = acceleratorRaw ? acceleratorRaw.toUpperCase() : t('overview.model_plan.unknown', 'Unknown');
      const recommendedValue = String(payload.recommended_plan || '').trim().toLowerCase() || 'auto';
      const selectedNode = byId('model_plan_selected');
      const recommendedNode = byId('model_plan_recommended');
      const hardwareNode = byId('model_plan_hardware');
      const descriptionNode = byId('model_plan_description');
      if (selectedNode) {
        selectedNode.textContent = tf('overview.model_plan.selected', {plan: modelPlanLabel(selectedValue)}, 'Selected: {plan}');
      }
      if (recommendedNode) {
        recommendedNode.textContent = tf('overview.model_plan.recommended', {plan: modelPlanLabel(recommendedValue)}, 'Auto recommends: {plan}');
      }
      if (hardwareNode) {
        const hasHardware = acceleratorRaw || Number(hardware.system_ram_gb || 0) > 0 || Number(hardware.gpu_vram_gb || 0) > 0;
        hardwareNode.textContent = hasHardware
          ? tf(
              'overview.model_plan.hardware',
              {
                accelerator: accelerator,
                vram: String(Number(hardware.gpu_vram_gb || 0).toFixed(1)),
                ram: String(Number(hardware.system_ram_gb || 0).toFixed(1)),
              },
              '{accelerator} | VRAM {vram} GB | RAM {ram} GB'
            )
          : t('overview.model_plan.hardware_unknown', 'Hardware detection unavailable');
      }
      if (descriptionNode) {
        descriptionNode.textContent = String(payload.description || '').trim();
      }
    }

    function renderSystemTelemetry(data) {
      const payload = data || ui.lastSystemStatus || {};
      syncCapabilitiesFromPayload(payload);
      const cpu = payload && payload.cpu ? payload.cpu : {};
      const ram = payload && payload.ram ? payload.ram : {};
      const gpus = Array.isArray(payload && payload.gpus) ? payload.gpus : [];
      const primaryGpu = gpus.length ? (gpus[0] || {}) : null;
      const modelPlanPayload = payload && payload.model_plan ? payload.model_plan : {};
      const hardware = modelPlanPayload.hardware || {};
      const acceleratorRaw = String(hardware.accelerator || '').trim();
      const accelerator = acceleratorRaw ? acceleratorRaw.toUpperCase() : t('overview.model_plan.unknown', 'Unknown');
      const gpuNames = gpus.length
        ? gpus.map(function (g) { return String(g.name || 'GPU'); }).join(' | ')
        : t('overview.resource.gpu_na', 'n/a');
      const hasCpuTelemetry = parseIntSafe(cpu.logical_count, 0) > 0;
      const cpuPercent = Number(cpu.percent || 0);
      const ramPercent = Number(ram.percent || 0);
      const vramPercent = primaryGpu ? Number(primaryGpu.vram_percent || 0) : null;

      const cpuNode = byId('overview_resource_cpu');
      if (cpuNode) {
        const logicalCount = parseIntSafe(cpu.logical_count, 0);
        cpuNode.textContent = logicalCount > 0
          ? tf(
              'overview.resource.cpu_value',
              {
                value: String(cpuPercent.toFixed(1)),
                count: String(logicalCount),
              },
              '{value}% of {count} threads'
            )
          : t('overview.resource.metric_unavailable', 'n/a');
      }

      const ramNode = byId('overview_resource_ram');
      if (ramNode) {
        ramNode.textContent = tf(
          'overview.resource.ram_value',
          {
            used: formatGiBFromBytes(ram.used),
            total: formatGiBFromBytes(ram.total),
            pct: String(ramPercent.toFixed(1)),
          },
          '{used} / {total} GB ({pct}%)'
        );
      }

      const gpuNode = byId('overview_resource_gpu');
      if (gpuNode) {
        gpuNode.textContent = primaryGpu
          ? tf(
              'overview.resource.gpu_value',
              {
                value: String(Number(primaryGpu.gpu_util || 0).toFixed(1)),
                name: String(primaryGpu.name || 'GPU0'),
              },
              '{value}% | {name}'
            )
          : t('overview.resource.gpu_na', 'n/a');
      }

      const vramNode = byId('overview_resource_vram');
      if (vramNode) {
        vramNode.textContent = primaryGpu
          ? tf(
              'overview.resource.vram_value',
              {
                used: formatGiBFromBytes(primaryGpu.vram_used),
                total: formatGiBFromBytes(primaryGpu.vram_total),
                pct: String(Number(primaryGpu.vram_percent || 0).toFixed(1)),
              },
              '{used} / {total} GB ({pct}%)'
            )
          : t('overview.resource.gpu_na', 'n/a');
      }

      const detailNode = byId('overview_resource_detail');
      if (detailNode) {
        const hasLimitedTelemetry = Boolean(
          acceleratorRaw ||
          gpuNames !== t('overview.resource.gpu_na', 'n/a') ||
          ram.total ||
          ram.used
        );
        detailNode.textContent = payload.sampled_at
          ? tf(
              'overview.resource.detail',
              {
                accelerator: accelerator,
                time: formatSampledTime(payload.sampled_at),
              },
              '{accelerator} | updated {time}'
            )
          : hasLimitedTelemetry
            ? tf(
                'overview.resource.detail_limited',
                {
                  accelerator: accelerator,
                },
                '{accelerator} | limited telemetry'
              )
            : t('overview.resource.detail_na', 'System telemetry unavailable.');
      }

      renderDashboardHealth(payload, ui.latestStatus);
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

    function syncCapabilitiesFromPayload(payload) {
      if (!payload || typeof payload !== 'object') return;
      if (payload.api_version) {
        ui.apiVersion = String(payload.api_version);
      }
      const caps = payload.capabilities;
      if (caps && typeof caps === 'object') {
        const names = Object.keys(ui.apiCapabilities || {});
        for (let i = 0; i < names.length; i += 1) {
          const name = names[i];
          if (Object.prototype.hasOwnProperty.call(caps, name)) {
            ui.apiCapabilities[name] = !!caps[name];
          }
        }
        return;
      }

      const looksLikeSystemPayload = (
        Object.prototype.hasOwnProperty.call(payload, 'ram') ||
        Object.prototype.hasOwnProperty.call(payload, 'gpus') ||
        Object.prototype.hasOwnProperty.call(payload, 'processes') ||
        Object.prototype.hasOwnProperty.call(payload, 'model_plan')
      );
      if (!looksLikeSystemPayload) return;

      if (!Object.prototype.hasOwnProperty.call(payload, 'cpu') || parseIntSafe(payload.cpu && payload.cpu.logical_count, 0) <= 0) {
        ui.apiCapabilities.system_cpu = false;
      }
      if (!Object.prototype.hasOwnProperty.call(payload, 'processes')) {
        ui.apiCapabilities.system_processes = false;
      }
      if (!Object.prototype.hasOwnProperty.call(payload, 'sampled_at') || !payload.sampled_at) {
        ui.apiCapabilities.system_sampled_at = false;
      }
      if (!Object.prototype.hasOwnProperty.call(payload, 'model_cache')) {
        ui.apiCapabilities.system_model_cache = false;
      }
    }

    function hasCapability(name, fallback) {
      if (!name) return fallback !== false;
      const value = ui.apiCapabilities ? ui.apiCapabilities[name] : null;
      if (value === true) return true;
      if (value === false) return false;
      return fallback !== false;
    }

    function isMissingEndpointError(err) {
      const text = String((err && err.message) || err || '').toLowerCase();
      return text.indexOf('not found') >= 0 || text.indexOf('404') >= 0;
    }

    async function runCapabilityTask(capabilityName, taskFn, fallbackValue) {
      if (capabilityName && !hasCapability(capabilityName, true)) {
        return fallbackValue;
      }
      try {
        return await taskFn();
      } catch (err) {
        if (capabilityName && isMissingEndpointError(err)) {
          ui.apiCapabilities[capabilityName] = false;
        }
        throw err;
      }
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

    function capabilityLabel(name) {
      const key = String(name || '').trim().toLowerCase();
      if (key === 'queue_api') return t('msg.capability.queue', 'queue');
      if (key === 'alerts_api') return t('msg.capability.alerts', 'alerts');
      if (key === 'capacity_api') return t('msg.capability.capacity', 'capacity');
      if (key === 'configs_api') return t('msg.capability.configs', 'config versions');
      if (key === 'system_processes' || key === 'system_cpu' || key === 'system_sampled_at') {
        return t('msg.capability.process_telemetry', 'process telemetry');
      }
      return key;
    }

    function composeCompatibilityMessage() {
      const disabled = Object.keys(ui.apiCapabilities || {}).filter(function (name) {
        return ui.apiCapabilities[name] === false;
      });
      if (!disabled.length) return '';
      const visible = [];
      for (let i = 0; i < disabled.length; i += 1) {
        const label = capabilityLabel(disabled[i]);
        if (visible.indexOf(label) < 0) visible.push(label);
      }
      return tf(
        'msg.compatibility_limited',
        {items: visible.join(', ')},
        'Compatibility mode: {items} unavailable in the current backend. Restart dashboard after the current run.'
      );
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
      ui.lastModuleJobsData = data || null;
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
      renderModuleSummary(data);
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
        renderModuleSummary(null);
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
      renderModuleSummary(data);
    }

    function renderModuleSummary(data) {
      const activeNode = byId('module_summary_active');
      const pendingNode = byId('module_summary_pending');
      const historyNode = byId('module_summary_history');
      const selectedNode = byId('module_summary_selected');
      const hintNode = byId('module_summary_hint');
      const jobsData = data && typeof data === 'object' && (data.active_job || data.pending_jobs || data.history)
        ? data
        : (ui.lastModuleJobsData || null);

      const active = jobsData && jobsData.active_job ? jobsData.active_job : null;
      const pending = Array.isArray(jobsData && jobsData.pending_jobs) ? jobsData.pending_jobs : [];
      const history = Array.isArray(jobsData && jobsData.history) ? jobsData.history : [];
      const hiddenCount = Object.keys(ui.hiddenModuleJobs || {}).length;

      if (activeNode) activeNode.textContent = active ? String(active.job_id || t('state.running', 'running')) : t('module.summary.none', 'None');
      if (pendingNode) pendingNode.textContent = String(pending.length);
      if (historyNode) historyNode.textContent = String(ui.moduleJobs.length);
      if (selectedNode) selectedNode.textContent = ui.moduleSelectedJobId || t('module.summary.none', 'None');
      if (hintNode) {
        hintNode.textContent = tf(
          'module.summary.hint_dynamic',
          {
            history: String(history.length),
            hidden: String(hiddenCount),
            type: String(active && active.job_type ? active.job_type : '-'),
          },
          'History {history} | Hidden {hidden} | Active type {type}'
        );
      }
    }

    function setTranslationTargetSelection(mode) {
      const checks = document.querySelectorAll('#module_trans_target_list input[type="checkbox"][data-lang]');
      for (let i = 0; i < checks.length; i += 1) {
        const input = checks[i];
        const code = String(input.getAttribute('data-lang') || '').toLowerCase();
        if (mode === 'all') input.checked = true;
        else if (mode === 'none') input.checked = false;
        else input.checked = (code === 'zh' || code === 'ja' || code === 'ko');
      }
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
        gallery.innerHTML = renderImageGalleryEmptyState();
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

    function currentSpeakerSourceMode() {
      const raw = byId('speaker_source_mode') ? String(byId('speaker_source_mode').value || '').trim().toLowerCase() : 'preset';
      return raw === 'custom' ? 'custom' : 'preset';
    }

    function setSpeakerSourceMode(mode) {
      const normalized = mode === 'custom' ? 'custom' : 'preset';
      if (byId('speaker_source_mode')) byId('speaker_source_mode').value = normalized;
      const presetPanel = byId('speaker_preset_panel');
      const customPanel = byId('speaker_custom_panel');
      if (presetPanel) presetPanel.hidden = normalized !== 'preset';
      if (customPanel) customPanel.hidden = normalized !== 'custom';
      const buttons = document.querySelectorAll('.speaker-source-btn');
      for (let i = 0; i < buttons.length; i += 1) {
        const button = buttons[i];
        if (!(button instanceof HTMLButtonElement)) continue;
        button.classList.toggle('active', String(button.dataset.sourceMode || '') === normalized);
      }
      syncSpeakerSelection();
    }

    function populateSelectOptions(selectId, items, emptyLabel, preferredValue) {
      const node = byId(selectId);
      if (!(node instanceof HTMLSelectElement)) return '';
      const choices = Array.isArray(items) ? items : [];
      const options = [];
      if (!choices.length) {
        options.push('<option value="">' + escapeHtml(emptyLabel) + '</option>');
      } else {
        for (let i = 0; i < choices.length; i += 1) {
          const item = choices[i] || {};
          const value = String(item.value || item.path || '');
          const label = String(item.label || item.name || value || emptyLabel);
          options.push('<option value="' + escapeHtml(value) + '">' + escapeHtml(label) + '</option>');
        }
      }
      node.innerHTML = options.join('');
      if (preferredValue) node.value = preferredValue;
      if (!node.value && choices.length) {
        node.value = String((choices[0] && (choices[0].value || choices[0].path)) || '');
      }
      return String(node.value || '');
    }

    function syncSpeakerSelection() {
      const speakerWavNode = byId('speaker_wav');
      if (!speakerWavNode) return;
      if (currentSpeakerSourceMode() === 'custom') {
        const customWavSelect = byId('speaker_custom_wav_select');
        speakerWavNode.value = customWavSelect ? String(customWavSelect.value || '').trim() : '';
      } else {
        speakerWavNode.value = '';
      }
    }

    function renderPresetSpeakerSamples(data) {
      const payload = data && typeof data === 'object' ? data : {};
      const samples = Array.isArray(payload.samples) ? payload.samples : [];
      ui.presetSpeakerSamples = samples;
      const defaults = payload.auto_defaults && typeof payload.auto_defaults === 'object' ? payload.auto_defaults : {};
      const autoTitle = byId('speaker_preset_auto_title');
      const autoMeta = byId('speaker_preset_auto_meta');
      const autoTags = byId('speaker_preset_auto_tags');
      const autoHint = byId('speaker_preset_auto_hint');
      const summaryEntries = Object.keys(defaults).map(function (language) {
        const samplePath = String(defaults[language] || '');
        const sampleName = samplePath ? samplePath.split('/').pop() : '';
        return {language: language, sample: sampleName};
      });
      const preferredOrder = ['en', 'zh', 'zh-cn', 'ja', 'de', 'es', 'fr', 'pt', 'tr'];
      summaryEntries.sort(function (a, b) {
        const ai = preferredOrder.indexOf(String(a.language));
        const bi = preferredOrder.indexOf(String(b.language));
        const ar = ai >= 0 ? ai : preferredOrder.length + 1;
        const br = bi >= 0 ? bi : preferredOrder.length + 1;
        if (ar !== br) return ar - br;
        return String(a.language).localeCompare(String(b.language));
      });

      if (autoTitle) {
        if (summaryEntries.length) {
          autoTitle.textContent = ui.language === 'zh-TW'
            ? '已啟用自動語言匹配'
            : 'Auto-match enabled';
        } else {
          autoTitle.textContent = ui.language === 'zh-TW'
            ? '找不到可用的預設樣本'
            : 'No preset samples available';
        }
      }
      if (autoMeta) {
        if (summaryEntries.length) {
          autoMeta.textContent = ui.language === 'zh-TW'
            ? '執行時會依語音語言自動選擇預設樣本。'
            : 'Preset voices are selected automatically by voice language at runtime.';
        } else {
          autoMeta.textContent = ui.language === 'zh-TW'
            ? '目前無法自動匹配語言樣本。'
            : 'Language auto-matching is currently unavailable.';
        }
      }
      if (autoTags) {
        if (summaryEntries.length) {
          autoTags.innerHTML = summaryEntries.map(function (entry) {
            return '<span class="speaker-auto-tag">' + escapeHtml(String(entry.language)) + '</span>';
          }).join('');
          autoTags.hidden = false;
        } else {
          autoTags.innerHTML = '';
          autoTags.hidden = true;
        }
      }
      if (autoHint) {
        const fallbackSample = String(payload.fallback_sample || '').split('/').pop() || '';
        autoHint.textContent = summaryEntries.length
          ? (ui.language === 'zh-TW'
              ? '支援語言：' + summaryEntries.map(function (entry) { return String(entry.language); }).join(' / ')
                + '；沒有匹配時會退回 ' + String(fallbackSample || 'en_sample.wav') + '。'
              : 'Supported languages: ' + summaryEntries.map(function (entry) { return String(entry.language); }).join(' / ')
                + '; fallback: ' + String(fallbackSample || 'en_sample.wav') + '.')
          : (ui.language === 'zh-TW'
              ? '目前沒有可自動匹配的預設樣本。'
              : 'No auto-matched preset samples are available.');
      }
      const rootHint = byId('speaker_preset_root_hint');
      if (rootHint) rootHint.textContent = 'Preset sample root: ' + String(payload.root || 'models/XTTS-v2/samples');
      if (currentSpeakerSourceMode() === 'preset' && byId('speaker_wav')) byId('speaker_wav').value = '';
    }

    function renderCustomSpeakerLibrary(data, preferredWav) {
      const payload = data && typeof data === 'object' ? data : {};
      const directories = Array.isArray(payload.directories) ? payload.directories : [];
      const files = Array.isArray(payload.files) ? payload.files : [];
      ui.customSpeakerDirs = directories;
      ui.customSpeakerFiles = files;

      const selectedDir = populateSelectOptions(
        'speaker_dir',
        directories.map(function (item) {
          const count = parseIntSafe(item.wav_count, 0);
          const suffix = count > 0 ? ' (' + String(count) + ')' : '';
          return {value: item.path, label: String(item.label || item.path || '') + suffix};
        }),
        'No custom folders',
        String(payload.selected_dir || payload.default_dir || '')
      );
      const selectedWav = populateSelectOptions(
        'speaker_custom_wav_select',
        files.map(function (item) {
          return {value: item.path, label: item.name};
        }),
        'No recordings yet',
        preferredWav
      );
      const rootHint = byId('speaker_custom_root_hint');
      if (rootHint) rootHint.textContent = 'Custom voice root: ' + String(payload.root || 'runs/voice_samples');
      if (currentSpeakerSourceMode() === 'custom') {
        if (byId('speaker_dir')) byId('speaker_dir').value = selectedDir;
        if (byId('speaker_wav')) byId('speaker_wav').value = selectedWav;
      }
    }

    async function refreshOverviewSpeakerLibraries(preferred) {
      const hints = preferred && typeof preferred === 'object' ? preferred : {};
      const desiredDir = String(
        hints.dir != null
          ? hints.dir
          : ((byId('speaker_dir') && byId('speaker_dir').value) || '')
      ).trim();
      const desiredWav = String(
        hints.wav != null
          ? hints.wav
          : ((byId('speaker_wav') && byId('speaker_wav').value) || '')
      ).trim();
      try {
        const [presetData, customData] = await Promise.all([
          apiGet('/api/voice/preset-samples'),
          apiGet('/api/voice/custom-speakers?selected_dir=' + encodeURIComponent(desiredDir)),
        ]);
        renderPresetSpeakerSamples(presetData);
        renderCustomSpeakerLibrary(customData, currentSpeakerSourceMode() === 'custom' ? desiredWav : '');
        syncSpeakerSelection();
      } catch (err) {
        setMessage(String((err && err.message) || err || 'Failed to load speaker library.'), 'warn');
      }
    }

    function payloadFromForm() {
      const seedRaw = byId('seed').value.trim();
      const inputMode = byId('story_input_mode').value || 'preset';
      const isCustom = inputMode === 'custom';
      const speakerMode = currentSpeakerSourceMode();
      syncSpeakerSelection();
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
        speaker_source_mode: speakerMode,
        speaker_wav: (byId('speaker_wav').value || '').trim() || null,
        speaker_dir: speakerMode === 'custom'
          ? ((byId('speaker_dir').value || '').trim() || null)
          : null,
        model_plan: byId('model_plan').value || 'auto',
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
      const inferredSpeakerMode = p.speaker_source_mode
        || (String(p.speaker_dir || '').replace(/\\/g, '/').startsWith('runs/voice_samples')
          || String(p.speaker_wav || '').replace(/\\/g, '/').startsWith('runs/voice_samples')
          ? 'custom'
          : 'preset');
      byId('speaker_wav').value = inferredSpeakerMode === 'custom' ? (p.speaker_wav || '') : '';
      if (byId('speaker_source_mode')) {
        byId('speaker_source_mode').value = inferredSpeakerMode;
      }
      byId('model_plan').value = p.model_plan || 'auto';
      byId('photo_enabled').checked = p.photo_enabled !== false;
      byId('translation_enabled').checked = p.translation_enabled !== false;
      byId('voice_enabled').checked = p.voice_enabled !== false;
      byId('verify_enabled').checked = p.verify_enabled !== false;
      byId('low_vram').checked = p.low_vram !== false;
      byId('strict_translation').checked = p.strict_translation !== false;
      byId('strict_voice').checked = p.strict_voice !== false;
      renderModelPlanStatus(ui.lastSystemStatus);
      renderSystemTelemetry(ui.lastSystemStatus);
      syncStrictOptionAvailability();
      syncStoryInputMode();
      setSpeakerSourceMode(currentSpeakerSourceMode());
      refreshOverviewSpeakerLibraries({
        dir: p.speaker_dir || '',
        wav: inferredSpeakerMode === 'custom' ? (p.speaker_wav || '') : '',
      });
    }

    function extractActiveRunPayload(status) {
      const active = status && typeof status === 'object' ? status.active_job : null;
      if (active && typeof active === 'object' && active.payload && typeof active.payload === 'object') {
        return active.payload;
      }
      const lastConfig = status && typeof status === 'object' ? status.last_config : null;
      if (lastConfig && typeof lastConfig === 'object') {
        return lastConfig;
      }
      return null;
    }

    function syncFormWithActiveRun(status) {
      const runId = String(status && status.run_id ? status.run_id : '').trim();
      const running = !!(status && status.running && runId);
      if (!running) {
        ui.formHydratedRunId = '';
        return;
      }

      if (ui.formHydratedRunId === runId) {
        return;
      }

      const payload = extractActiveRunPayload(status);
      if (!payload || typeof payload !== 'object' || !Object.keys(payload).length) {
        return;
      }

      setFormFromPayload(payload);
      ui.formHydratedRunId = runId;
      try {
        localStorage.setItem(STORE_KEY, JSON.stringify(payload));
      } catch (_err) {
      }
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
      renderKgSummary();
      renderDemoStoryline();
    }

    function currentDemoStep() {
      if (ui.activeTab === 'modules') return 3;
      if (ui.activeTab === 'evaluation') return 4;
      const mode = (byId('story_input_mode') && byId('story_input_mode').value) || 'preset';
      return mode === 'custom' ? 2 : 1;
    }

    function renderDemoStoryline() {
      const step = currentDemoStep();
      const focusNode = byId('demo_storyline_focus');
      if (focusNode) {
        setPillTone(focusNode, step >= 3 ? 'warning' : 'info', t('demo.storyline.focus.step' + String(step), 'Step ' + String(step)));
      }

      const cards = document.querySelectorAll('.demo-step-card[data-step]');
      for (let i = 0; i < cards.length; i += 1) {
        const card = cards[i];
        const cardStep = parseIntSafe(card.getAttribute('data-step'), 0);
        if (cardStep === step) card.classList.add('is-active');
        else card.classList.remove('is-active');
      }
    }

    function renderKgSummary() {
      const autoText = t('module.option.auto', 'Auto');
      const mode = (byId('story_input_mode') && byId('story_input_mode').value) || 'preset';
      const isCustom = mode === 'custom';
      const age = ((byId('age') && byId('age').value) || '').trim() || autoText;
      const category = ((byId('category') && byId('category').value) || '').trim() || autoText;
      const theme = (isCustom
        ? ((byId('theme_custom') && byId('theme_custom').value) || '')
        : ((byId('theme') && byId('theme').value) || '')
      ).trim() || autoText;
      const subcategory = (isCustom
        ? ((byId('subcategory_custom') && byId('subcategory_custom').value) || '')
        : ((byId('subcategory') && byId('subcategory').value) || '')
      ).trim() || autoText;
      const promptText = ((byId('story_prompt') && byId('story_prompt').value) || '').trim();
      const materialsText = ((byId('story_materials') && byId('story_materials').value) || '').trim();
      const promptCount = promptText ? 1 : 0;
      const materialCount = materialsText
        ? materialsText.split(/\r?\n/).map(function (line) { return line.trim(); }).filter(Boolean).length
        : 0;
      const selectedPlan = ((byId('model_plan') && byId('model_plan').value) || 'auto').trim() || 'auto';
      const recommendedPlan = String(
        (((ui.lastSystemStatus || {}).model_plan || {}).recommended_plan) || selectedPlan || 'auto'
      ).trim() || 'auto';
      const outputs = [];
      if (byId('photo_enabled') && byId('photo_enabled').checked) outputs.push(t('overview.toggle.photo', 'Photo'));
      if (byId('translation_enabled') && byId('translation_enabled').checked) outputs.push(t('overview.toggle.translation', 'Translation'));
      if (byId('voice_enabled') && byId('voice_enabled').checked) outputs.push(t('overview.toggle.voice', 'Voice'));
      if (byId('verify_enabled') && byId('verify_enabled').checked) outputs.push(t('overview.toggle.verify', 'Verify'));

      const modeNode = byId('kg_summary_mode');
      const sourceNode = byId('kg_summary_source');
      const scopeNode = byId('kg_summary_scope');
      const planNode = byId('kg_summary_plan');
      const pillNode = byId('kg_summary_mode_pill');
      if (modeNode) modeNode.textContent = t(isCustom ? 'kg.summary.mode_custom' : 'kg.summary.mode_preset', isCustom ? 'Custom' : 'Preset');
      if (sourceNode) sourceNode.textContent = t(isCustom ? 'kg.summary.source_custom' : 'kg.summary.source_preset', isCustom ? 'KG + normalized user intent' : 'KG defaults');
      if (scopeNode) scopeNode.textContent = tf('kg.summary.scope', {age: age, category: category}, age + ' / ' + category);
      if (planNode) {
        const selectedLabel = modelPlanLabel(selectedPlan);
        const recommendedLabel = modelPlanLabel(recommendedPlan);
        planNode.textContent = selectedPlan === 'auto' || selectedLabel === recommendedLabel
          ? selectedLabel
          : (selectedLabel + ' | Auto: ' + recommendedLabel);
      }
      if (pillNode) {
        setPillTone(
          pillNode,
          isCustom ? 'warning' : 'info',
          t(isCustom ? 'kg.summary.pill_custom' : 'kg.summary.pill_preset', isCustom ? 'KG + User' : 'KG')
        );
      }

      const points = [
        t(isCustom ? 'kg.summary.point.custom' : 'kg.summary.point.preset', ''),
        t(isCustom ? 'kg.summary.point.evidence_custom' : 'kg.summary.point.evidence_preset', ''),
        tf(
          'kg.summary.point.outputs',
          {outputs: outputs.length ? outputs.join(' / ') : t('module.summary.none', 'None')},
          'Enabled output chain: ' + (outputs.length ? outputs.join(' / ') : t('module.summary.none', 'None'))
        ),
        tf(
          isCustom ? 'kg.summary.point.scope_custom' : 'kg.summary.point.scope_preset',
          {
            theme: theme,
            subcategory: subcategory,
            prompts: String(promptCount),
            materials: String(materialCount),
          },
          ''
        )
      ].filter(Boolean);

      const pointsNode = byId('kg_summary_points');
      if (pointsNode) {
        pointsNode.innerHTML = points.map(function (text) {
          return '<div class="list-item advisory-info">' + escapeHtml(String(text)) + '</div>';
        }).join('');
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
      setSpeakerSourceMode('custom');
      const reader = new FileReader();
      reader.onload = async function () {
        try {
          const dataUrl = String(reader.result || '');
          const base64 = dataUrl.split(',')[1] || '';
          const scriptText = (byId('voice_script').value || '').trim();
          const speakerDir = (byId('speaker_dir') && byId('speaker_dir').value)
            ? String(byId('speaker_dir').value || '').trim()
            : '';
          const result = await apiPost('/api/voice/recordings/save', {
            wav_base64: base64,
            sample_rate: ui.recordSampleRate || 16000,
            script_text: scriptText,
            speaker_dir: speakerDir || null,
          });
          if (result && result.path) {
            byId('speaker_wav').value = String(result.path);
            await refreshOverviewSpeakerLibraries({
              dir: String(result.dir || speakerDir || ''),
              wav: String(result.path),
            });
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
            speaker_dir: ((byId('module_voice_speaker_dir') && byId('module_voice_speaker_dir').value) || '').trim() || null,
          });
          if (result && result.path) {
            if (result.dir && byId('module_voice_speaker_dir')) {
              byId('module_voice_speaker_dir').value = String(result.dir);
            }
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
        payload.model_plan = 'portable';
        payload.translation_enabled = false;
        payload.voice_enabled = false;
        payload.verify_enabled = true;
        payload.low_vram = true;
        payload.strict_translation = false;
        payload.strict_voice = false;
      } else if (name === 'quality') {
        payload.max_retries = 2;
        payload.priority = 'high';
        payload.model_plan = 'quality';
        payload.translation_enabled = true;
        payload.voice_enabled = true;
        payload.verify_enabled = true;
        payload.low_vram = false;
        payload.strict_translation = true;
        payload.strict_voice = true;
      } else {
        payload.max_retries = 1;
        payload.priority = 'normal';
        payload.model_plan = 'balanced';
        payload.translation_enabled = true;
        payload.voice_enabled = true;
        payload.verify_enabled = true;
        payload.low_vram = true;
        payload.strict_translation = true;
        payload.strict_voice = true;
      }
      setFormFromPayload(payload);
      setMessage(
        tf(
          'msg.preset_applied',
          {name: t('overview.preset.' + name, name)},
          'Preset applied: {name}',
        ),
        'ok',
      );
    }

    function setStatePill(text, state) {
      const el = byId('pill_state');
      el.textContent = localizeState(text);
      el.className = 'pill';
      if (state) el.classList.add(state);
    }

    function syncStrictOptionAvailability() {
      const translationEnabled = !!(byId('translation_enabled') && byId('translation_enabled').checked);
      const voiceEnabled = !!(byId('voice_enabled') && byId('voice_enabled').checked);
      const strictTranslation = byId('strict_translation');
      const strictVoice = byId('strict_voice');
      const strictTranslationChip = byId('strict_translation_chip');
      const strictVoiceChip = byId('strict_voice_chip');

      if (strictTranslation) strictTranslation.disabled = !translationEnabled;
      if (strictVoice) strictVoice.disabled = !voiceEnabled;
      if (strictTranslationChip) strictTranslationChip.classList.toggle('disabled', !translationEnabled);
      if (strictVoiceChip) strictVoiceChip.classList.toggle('disabled', !voiceEnabled);
    }

    function updatePreEvalPanel(preEvaluation, currentStage) {
      const panel = byId('pre_eval_panel');
      if (!panel) return {visible: false, state: 'idle'};

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
      const hasPayloadData = Number.isFinite(overallScore) ||
        Number.isFinite(coherenceScore) ||
        Number.isFinite(entityScore) ||
        !!payload.policy ||
        !!payload.gate_message ||
        !!payload.error;
      const visible = state === 'running' || state === 'completed' || state === 'degraded' || state === 'blocked' || hasPayloadData;
      panel.hidden = !visible;

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

      return {visible: visible, state: state};
    }

    function updateHeaderKpis(statusData, capacityData) {
      const stateNode = byId('kpi_system_state');
      const queueNode = byId('kpi_queue_depth');
      const progressNode = byId('kpi_success_rate');
      const elapsedNode = byId('kpi_avg_duration');
      const updatedNode = byId('kpi_gpu_cost');
      if (!stateNode || !queueNode || !progressNode || !elapsedNode || !updatedNode) return;

      const runner = statusData && statusData.runner ? statusData.runner : {};
      const state = Boolean(statusData && statusData.running)
        ? 'running'
        : String(runner.state || 'idle');
      stateNode.textContent = localizeState(state);
      queueNode.textContent = String(statusData && Number.isFinite(Number(statusData.queue_depth)) ? statusData.queue_depth : 0);
      progressNode.textContent = Number.isFinite(Number(statusData && statusData.progress_pct))
        ? (Number(statusData.progress_pct).toFixed(1) + '%')
        : '-';
      elapsedNode.textContent = formatDuration(statusData ? statusData.elapsed_sec : null);
      updatedNode.textContent = statusData && statusData.updated_ago_sec != null
        ? (String(Math.round(Number(statusData.updated_ago_sec || 0))) + 's')
        : '-';
    }

    function renderStatus(data) {
      syncFormWithActiveRun(data);
      syncCapabilitiesFromPayload(data);
      ui.latestStatus = data;
      updateHeaderKpis(data, ui.lastCapacity || {});
      renderOpsSummary();
      function setNodeText(id, value) {
        const node = byId(id);
        if (node) node.textContent = value;
      }
      const runner = data.runner || {};
      const state = String(runner.state || (data.running ? 'running' : 'idle')).toLowerCase();
      const total = parseIntSafe(runner.total_books, 0);
      const completed = parseIntSafe(runner.completed_books, 0);
      const success = parseIntSafe(runner.success_books, 0);
      const failed = parseIntSafe(runner.failed_books, 0);
      const remaining = Math.max(0, total - completed);
      setStatePill(state, state);
      const health = renderDashboardHealth(ui.lastSystemStatus, data);
      updatePreEvalPanel(runner.pre_evaluation, runner.current_stage);

      const bookPillLabel = Boolean(data.running)
        ? t('meta.book', 'book')
        : t('overview.monitor.last_run.books', 'books');
      const bookPillValue = Boolean(data.running)
        ? String(runner.current_book == null ? '-' : runner.current_book)
        : (total > 0 ? (String(completed) + '/' + String(total)) : '-');
      byId('pill_book').textContent = bookPillLabel + ': ' + bookPillValue;
      byId('pill_stage').textContent = t('meta.stage', 'stage') + ': ' + String(runner.current_stage || '-');
      const stageText = String(runner.current_stage || '-');
      const successRate = completed > 0 ? ((success / completed) * 100) : 0;

      let progress = parseFloatSafe(data.progress_pct, Number.NaN);
      if (!Number.isFinite(progress)) {
        progress = total > 0 ? (completed / total) * 100 : 0;
      }
      progress = Math.max(0, Math.min(100, progress));
      byId('progress_fill').style.width = String(progress) + '%';
      setNodeText('progress_label', progress.toFixed(1) + '%');
      let progressDetail = tf(
        'overview.progress.detail',
        {
          done: String(completed),
          total: String(total),
          remaining: String(remaining),
        },
        '{done}/{total} completed | {remaining} remaining'
      );
      const stageProgress = (runner && runner.stage_progress && typeof runner.stage_progress === 'object')
        ? runner.stage_progress
        : ((data && data.stage_progress && typeof data.stage_progress === 'object') ? data.stage_progress : null);
      const stageDetail = String((data && data.stage_detail) || (runner && runner.stage_detail) || '').trim();
      if (stageProgress) {
        const phase = String(stageProgress.phase || stageText || '').trim();
        const current = Number.isFinite(Number(stageProgress.completed)) ? Number(stageProgress.completed) : 0;
        const totalStage = Number.isFinite(Number(stageProgress.total)) ? Number(stageProgress.total) : 0;
        const taskLabel = String(stageProgress.task_label || stageDetail || '').trim();
        const taskIndex = Number.isFinite(Number(stageProgress.task_index)) ? Number(stageProgress.task_index) : 0;
        const taskTotal = Number.isFinite(Number(stageProgress.task_total)) ? Number(stageProgress.task_total) : 0;
        const stageParts = [];
        if (totalStage > 0) {
          stageParts.push(`${current}/${totalStage}`);
        }
        if (phase) {
          stageParts.push(phase.toUpperCase());
        }
        if (taskTotal > 0) {
          stageParts.push(`${taskIndex}/${taskTotal}`);
        }
        if (taskLabel) {
          stageParts.push(taskLabel);
        }
        if (stageParts.length > 0) {
          progressDetail += ' | ' + stageParts.join(' | ');
        }
      }
      setNodeText('progress_detail', progressDetail);

      setNodeText('metric_success', String(success));
      setNodeText('metric_failed', String(failed));
      setNodeText('metric_eta', formatDuration(data.eta_sec));

      setNodeText('meta_run_id', String(data.run_id || '-'));
      setNodeText('meta_exit_code', data.exit_code == null ? '-' : String(data.exit_code));
      renderOverviewMonitor(data, health);

      byId('raw_status').textContent = JSON.stringify(data, null, 2);

      const startDisabled = Boolean(data.running) && (data.queue_depth || 0) >= 1;
      byId('btn_start').disabled = startDisabled;
      byId('btn_stop').disabled = !Boolean(data.running);

      const currentRunId = data.run_id || null;
      if (currentRunId !== ui.activeLogRunId) {
        ui.activeLogRunId = currentRunId;
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
      ui.lastLogReceiptTs = Date.now();
      const overviewBox = byId('overview_log_output');
      if (!overviewBox) return;
      let chunk = '';
      for (let i = 0; i < lines.length; i += 1) {
        const line = lines[i] || {};
        const ts = line.ts ? String(line.ts).slice(11, 19) : '--:--:--';
        const txt = line.text ? String(line.text) : '';
        chunk += '[' + ts + '] ' + txt + '\n';
      }
      overviewBox.textContent += chunk;
      const rows = overviewBox.textContent.split('\n');
      if (rows.length > 260) {
        overviewBox.textContent = rows.slice(rows.length - 260).join('\n');
      }
      overviewBox.scrollTop = overviewBox.scrollHeight;
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

    function syncEvaluationAdvancedControls() {
      const toggle = byId('btn_eval_advanced');
      const panel = byId('eval_advanced_panel');
      const branchNode = byId('evaluation_branch');
      if (!toggle || !panel || !branchNode) return;

      const branch = String(branchNode.value || ui.evaluation.branch || 'canonical').trim() || 'canonical';
      const isDefaultBranch = branch.toLowerCase() === 'canonical';
      const expanded = !isDefaultBranch || !!ui.evaluation.showAdvanced;

      panel.hidden = !expanded;
      toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      toggle.classList.toggle('active', expanded);
      toggle.textContent = isDefaultBranch
        ? t(expanded ? 'eval.advanced.hide' : 'eval.advanced.show', expanded ? 'Hide advanced' : 'Advanced options')
        : tf('eval.advanced.custom', {value: branch}, 'Advanced: {value}');
    }

    function evaluationRequestKey(source, runId, book, storyRoot, branch) {
      return [
        String(source || 'latest').trim(),
        String(runId || '').trim(),
        String(book || '').trim(),
        String(storyRoot || '').trim(),
        String(branch || 'canonical').trim().toLowerCase(),
      ].join('||');
    }

    function evaluationRenderSignature(payload) {
      try {
        return JSON.stringify(payload || {});
      } catch (_err) {
        return String(Date.now());
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
        setEvaluationChartPlaceholder(true);
        renderEvaluationInsights(null, null);
        const localizedErrorText = localizeBackendMessage(payload.error || t('msg.eval_no_data', 'No evaluation loaded.'));

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
          logsNode.textContent = String(localizedErrorText);
        }

        if (!preserveStatus) {
          setEvaluationStatus(String(localizedErrorText || t('msg.eval_fetch_failed', 'Failed to load evaluation report.')), 'warn');
        }
        return;
      }

      const diagnostics = payload.diagnostics && typeof payload.diagnostics === 'object' ? payload.diagnostics : {};
      renderEvaluationInsights(diagnostics, payloadSelectedBook);
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
      const dimensionOrder = ['readability', 'factuality', 'emotional_impact', 'completeness', 'entity_consistency', 'coherence', 'multimodal_alignment'];
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
        multimodal_alignment: '文圖一致性',
      };
      const dimensionLabelsEn = {
        readability: 'Readability',
        factuality: 'Factuality',
        emotional_impact: 'Emotional Impact',
        completeness: 'Completeness',
        entity_consistency: 'Entity Consistency',
        coherence: 'Coherence',
        multimodal_alignment: 'Multimodal Alignment',
      };
      const dimensionMap = ui.language === 'zh-TW'
        ? {
            readability: '可讀性',
            factuality: '事實性',
            emotional_impact: '情感影響',
            completeness: '完整性',
            entity_consistency: '角色一致性',
            coherence: '連貫性',
            multimodal_alignment: '文圖一致性',
          }
        : dimensionLabelsEn;
      const chartLabels = [];
      const values = [];
      for (let i = 0; i < dimensions.length; i += 1) {
        const key = dimensions[i];
        values.push(parseFloatSafe(scoreMap[key], 0));
        chartLabels.push(dimensionMap[key] || key.replace(/_/g, ' '));
      }

      clearEvaluationChart();
      const chartCanvas = byId('evalRadarChart');
      setEvaluationChartPlaceholder(!(chartCanvas && dimensions.length && window.Chart));
      if (chartCanvas && dimensions.length && window.Chart) {
        setEvaluationChartPlaceholder(false);
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

    function renderEvaluationInsights(diagnostics, selectedBook) {
      const summaryNode = byId('eval_dimension_summary');
      const findingsNode = byId('eval_findings_list');
      if (!summaryNode || !findingsNode) return;

      const scoreMap = diagnostics && diagnostics.dimension_scores && typeof diagnostics.dimension_scores === 'object'
        ? diagnostics.dimension_scores
        : {};
      const entries = Object.keys(scoreMap).map(function (key) {
        return {
          key: key,
          value: parseFloatSafe(scoreMap[key], 0),
        };
      }).sort(function (a, b) {
        return b.value - a.value;
      });

      if (!entries.length) {
        summaryNode.innerHTML = '<div class="mini">' + escapeHtml(t('eval.insight.empty_summary', 'No evaluation loaded.')) + '</div>';
        findingsNode.innerHTML = '<div class="list-item">' + escapeHtml(t('eval.insight.empty_findings', 'Key findings will appear here.')) + '</div>';
        return;
      }

      summaryNode.innerHTML = entries.map(function (item) {
        const label = String(item.key || '').replace(/_/g, ' ');
        return '<div class="mini">' +
          '<span>' + escapeHtml(label) + '</span>' +
          '<strong>' + escapeHtml(item.value.toFixed(1)) + '</strong>' +
          '</div>';
      }).join('');

      const strongest = entries[0];
      const weakest = entries[entries.length - 1];
      const findings = [];
      findings.push({
        title: t('eval.insight.strongest', 'Strongest dimension'),
        detail: tf('eval.insight.strongest_detail', {name: String(strongest.key).replace(/_/g, ' '), score: strongest.value.toFixed(1)}, '{name} scored {score}.'),
        level: 'info',
      });
      findings.push({
        title: t('eval.insight.weakest', 'Weakest dimension'),
        detail: tf('eval.insight.weakest_detail', {name: String(weakest.key).replace(/_/g, ' '), score: weakest.value.toFixed(1)}, '{name} scored {score}.'),
        level: weakest.value < 65 ? 'warning' : 'info',
      });

      if (selectedBook && selectedBook.story_root) {
        findings.push({
          title: t('eval.insight.scope', 'Selected evaluation scope'),
          detail: tf(
            'eval.insight.scope_detail',
            {book: formatBookOptionLabel(selectedBook, parseIntSafe(selectedBook.book_index, 1)), story_root: String(selectedBook.story_root)},
            'Book {book} from {story_root}'
          ),
          level: 'info',
        });
      }

      const listFields = ['issues', 'warnings', 'findings', 'recommendations'];
      for (let i = 0; i < listFields.length; i += 1) {
        const key = listFields[i];
        const value = diagnostics ? diagnostics[key] : null;
        if (!Array.isArray(value) || !value.length) continue;
        for (let j = 0; j < value.length && findings.length < 6; j += 1) {
          const titleMap = {
            issues: t('eval.insight.issues', 'Issues'),
            warnings: t('eval.insight.warnings', 'Warnings'),
            findings: t('eval.insight.findings', 'Findings'),
            recommendations: t('eval.insight.recommendations', 'Recommendations'),
          };
          findings.push({
            title: titleMap[key] || key,
            detail: String(value[j]),
            level: key === 'issues' || key === 'warnings' ? 'warning' : 'info',
          });
        }
      }

      findingsNode.innerHTML = findings.map(function (item) {
        return '<div class="list-item advisory-' + escapeHtml(item.level || 'info') + '">' +
          '<strong>' + escapeHtml(item.title || 'Finding') + '</strong>' +
          '<div class="meta">' + escapeHtml(item.detail || '') + '</div>' +
          '</div>';
      }).join('');
    }

    async function fetchEvaluation(force, options) {
      if (!force && ui.activeTab !== 'evaluation') return null;
      const opts = options && typeof options === 'object' ? options : {};

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

      const requestKey = evaluationRequestKey(
        ui.evaluation.source,
        ui.evaluation.runId,
        ui.evaluation.book,
        ui.evaluation.storyRoot,
        ui.evaluation.branch
      );
      const showLoading = Object.prototype.hasOwnProperty.call(opts, 'showLoading')
        ? !!opts.showLoading
        : !!force;
      const preserveStatus = Object.prototype.hasOwnProperty.call(opts, 'preserveStatus')
        ? !!opts.preserveStatus
        : !showLoading;
      const minBackgroundRefreshMs = Math.max(2500, parseIntSafe(opts.minRefreshMs, 6000));

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

      if (!force && ui.evaluation.pendingPromise && ui.evaluation.pendingKey === requestKey) {
        return ui.evaluation.pendingPromise;
      }
      if (!force && ui.evaluation.lastFetchKey === requestKey && (Date.now() - Number(ui.evaluation.lastFetchAt || 0)) < minBackgroundRefreshMs) {
        return ui.evaluation.lastResponse || null;
      }

      if (showLoading) {
        setEvaluationStatus(t('msg.eval_loading', 'Loading evaluation report...'), 'ok');
      }

      const requestPromise = (async function () {
        try {
          const data = await apiGet('/api/evaluation?' + params.toString());
          ui.evaluation.lastFetchAt = Date.now();
          ui.evaluation.lastFetchKey = requestKey;
          const signature = evaluationRenderSignature(data);
          if (!showLoading) {
            setEvaluationStatus('', '');
          }
          const shouldRender = signature !== ui.evaluation.renderSignature;
          if (shouldRender) {
            ui.evaluation.renderSignature = signature;
            renderEvaluation(data, {preserveStatus: preserveStatus});
          } else if (!preserveStatus) {
            setEvaluationStatus('', '');
          }
          ui.evaluation.lastResponse = data;
          return data;
        } catch (err) {
          const message = String((err && err.message) || err || t('msg.eval_fetch_failed', 'Failed to load evaluation report.'));
          setEvaluationStatus(message, 'bad');
          renderEvaluation({ok: false, error: message}, {preserveStatus: false});
          return null;
        } finally {
          if (ui.evaluation.pendingKey === requestKey) {
            ui.evaluation.pendingPromise = null;
            ui.evaluation.pendingKey = '';
          }
        }
      })();

      ui.evaluation.pendingKey = requestKey;
      ui.evaluation.pendingPromise = requestPromise;
      return requestPromise;
    }

    function renderQueue(data) {
      const unavailable = data == null && !hasCapability('queue_api', true);
      ui.lastQueue = unavailable ? {} : (data || {});
      const body = byId('queue_body');
      if (unavailable) {
        body.innerHTML = '<tr><td colspan="7">' + escapeHtml(t('msg.queue_unavailable', 'Queue data is unavailable in the current backend.')) + '</td></tr>';
        renderOpsSummary();
        return;
      }
      const payload = data || {};
      const active = payload.active_job;
      const pending = Array.isArray(payload.pending_jobs) ? payload.pending_jobs : [];
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
      renderOpsSummary();
    }

    function renderAlerts(items) {
      const unavailable = items == null && !hasCapability('alerts_api', true);
      ui.lastAlerts = unavailable ? [] : (Array.isArray(items) ? items : []);
      const list = byId('alert_list');
      if (unavailable) {
        list.innerHTML = '<div class="list-item">' + escapeHtml(t('msg.alerts_unavailable', 'Alert data is unavailable in the current backend.')) + '</div>';
        renderOpsSummary();
        return;
      }
      if (!Array.isArray(items) || !items.length) {
        list.innerHTML = '<div class="list-item">' + escapeHtml(t('msg.no_alerts', 'No alerts.')) + '</div>';
        renderOpsSummary();
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
      renderOpsSummary();
    }

    function renderCapacity(data) {
      const unavailable = data == null && !hasCapability('capacity_api', true);
      ui.lastCapacity = unavailable ? {} : (data || {});
      updateHeaderKpis(ui.latestStatus || {}, ui.lastCapacity || {});
      if (unavailable) {
        byId('cap_runs').textContent = '-';
        byId('cap_success_rate').textContent = '-';
        byId('cap_throughput').textContent = '-';
        byId('cap_queue_delay').textContent = '-';
        byId('cap_gpu_hours').textContent = '-';
        byId('cap_gpu_cost').textContent = '-';
        const unavailableTrend = byId('capacity_trend');
        if (unavailableTrend) {
          unavailableTrend.innerHTML = '<div class="list-item">' + escapeHtml(t('msg.capacity_unavailable', 'Capacity analytics are unavailable in the current backend.')) + '</div>';
        }
        renderOpsSummary();
        return;
      }
      const payload = data || {};
      byId('cap_runs').textContent = String(payload.window_runs || 0);
      byId('cap_success_rate').textContent = toPercent(payload.success_rate_pct || 0);
      byId('cap_throughput').textContent = String(parseFloatSafe(payload.books_per_hour, 0).toFixed(2));
      byId('cap_queue_delay').textContent = formatDuration(payload.avg_queue_delay_sec || 0);
      byId('cap_gpu_hours').textContent = String(parseFloatSafe(payload.gpu_hours, 0).toFixed(2));
      byId('cap_gpu_cost').textContent = '$' + parseFloatSafe(payload.gpu_cost_usd, 0).toFixed(2);

      const trend = byId('capacity_trend');
      const rows = Array.isArray(payload.trend) ? payload.trend : [];
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
      renderOpsSummary();
    }

    function renderOpsSummary() {
      const queueData = ui.lastQueue || {};
      const alerts = Array.isArray(ui.lastAlerts) ? ui.lastAlerts : [];
      const capacity = ui.lastCapacity || {};
      const queueAvailable = hasCapability('queue_api', true);
      const alertsAvailable = hasCapability('alerts_api', true);
      const capacityAvailable = hasCapability('capacity_api', true);
      const configsAvailable = hasCapability('configs_api', true);
      const active = queueData && queueData.active_job ? queueData.active_job : null;
      const pending = Array.isArray(queueData && queueData.pending_jobs) ? queueData.pending_jobs : [];
      const status = ui.latestStatus || {};
      const hasCritical = alerts.some(function (item) {
        const level = String((item && item.level) || '').toLowerCase();
        return level === 'critical' || level === 'error';
      });
      const hasWarning = alerts.some(function (item) {
        return String((item && item.level) || '').toLowerCase() === 'warning';
      });
      let opsHealth = 'Stable';
      if (hasCritical) opsHealth = healthLabel('critical');
      else if (hasWarning || pending.length >= 4) opsHealth = healthLabel('warning');
      else if (!queueAvailable || !alertsAvailable || !capacityAvailable || !configsAvailable) opsHealth = t('ops.summary.health_limited', 'Limited');
      else opsHealth = healthLabel('stable');

      const activeNode = byId('ops_summary_active');
      if (activeNode) {
        activeNode.textContent = active
          ? tf('ops.summary.running_job', {job: String(active.job_id || '')}, 'Running {job}')
          : (Boolean(status.running) ? t('state.running', 'running') : t('state.idle', 'idle'));
      }
      const queueNode = byId('ops_summary_queue');
      if (queueNode) {
        queueNode.textContent = queueAvailable
          ? String(pending.length)
          : (status.queue_depth == null ? '-' : String(status.queue_depth));
      }
      const alertsNode = byId('ops_summary_alerts');
      if (alertsNode) {
        alertsNode.textContent = alertsAvailable
          ? String(alerts.filter(function (item) { return !item.acknowledged; }).length)
          : '-';
      }
      const modulesNode = byId('ops_summary_modules');
      if (modulesNode) {
        const activeModule = status && status.module_active_job ? 1 : 0;
        const moduleQueue = parseIntSafe(status.module_queue_depth, 0);
        modulesNode.textContent = String(activeModule + moduleQueue);
      }
      const healthNode = byId('ops_summary_health');
      if (healthNode) healthNode.textContent = opsHealth;
      const hintNode = byId('ops_summary_hint');
      if (hintNode) {
        if (!capacityAvailable) {
          hintNode.textContent = t('ops.summary.hint_unavailable', 'Historical capacity metrics are unavailable in the current backend.');
        } else {
          hintNode.textContent = tf(
            'ops.summary.hint_dynamic',
            {
              success: toPercent(capacity.success_rate_pct || 0),
              delay: formatDuration(capacity.avg_queue_delay_sec || 0),
              cost: '$' + parseFloatSafe(capacity.gpu_cost_usd, 0).toFixed(2),
            },
            'Success {success} | Avg queue delay {delay} | GPU cost {cost}'
          );
        }
      }
    }

    function renderConfigVersions(items) {
      const body = byId('config_versions_body');
      const unavailable = items == null && !hasCapability('configs_api', true);
      if (unavailable) {
        body.innerHTML = '<tr><td colspan="5">' + escapeHtml(t('msg.configs_unavailable', 'Config versions are unavailable in the current backend.')) + '</td></tr>';
        renderOpsSummary();
        return;
      }
      if (!Array.isArray(items) || !items.length) {
        body.innerHTML = '<tr><td colspan="5">' + escapeHtml(t('msg.no_saved_versions', 'No saved versions.')) + '</td></tr>';
        renderOpsSummary();
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
      renderOpsSummary();
    }

    function renderRunDetail(data) {
      const run = data.run || {};
      const runId = String(run.run_id || ui.selectedRunId || '').trim();
      const selectedBook = updateDetailBookSelect(data, runId);
      const selectedBookLabel = selectedBook ? formatBookOptionLabel(selectedBook, parseIntSafe(selectedBook.book_index, 1)) : '-';
      const artifactRun = String((selectedBook && selectedBook.artifact_run) || '').trim();
      const storyRootValue = String((selectedBook && selectedBook.story_root) || run.story_root || '-');
      const lastStageValue = String(run.current_stage || '-');
      const evalReadyValue = run.evaluation_ready
        ? t('detail.artifact.eval_ready', 'Ready')
        : t('detail.artifact.eval_pending', 'Not ready');
      const logsScope = String(data.logs_scope || 'run').trim().toLowerCase();
      const logsSource = String(data.logs_source || artifactRun || '').trim();

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
      byId('detail_artifact_story_root').textContent = storyRootValue;
      byId('detail_artifact_book').textContent = selectedBookLabel;
      byId('detail_artifact_stage').textContent = artifactRun || lastStageValue;
      byId('detail_artifact_eval').textContent = evalReadyValue;
      byId('detail_json').textContent = JSON.stringify(data, null, 2);
      byId('detail_artifact_label_stage').textContent = artifactRun
        ? t('detail.artifact.run_capture', 'Log Capture')
        : t('detail.artifact.stage', 'Last Stage');
      byId('detail_timeline_title').textContent = t('detail.timeline.run_title', 'Run Timeline and Alerts');
      byId('detail_timeline_sub').textContent = selectedBook
        ? t('detail.timeline.run_sub', 'Timeline and alerts remain run-level for the whole batch.')
        : t('detail.timeline.sub', 'Run-level events and alerts for the whole batch.');
      byId('detail_logs_title').textContent = logsScope === 'book' && selectedBook
        ? tf('detail.logs.book_title', {book: selectedBookLabel}, '{book} Logs')
        : t('detail.logs.title', 'Run Logs');
      byId('detail_logs_sub').textContent = logsScope === 'book'
        ? (logsSource
            ? tf('detail.logs.book_sub_source', {source: logsSource}, 'Showing the latest captured terminal log for this book: {source}')
            : t('detail.logs.book_sub', 'Showing the latest captured terminal log for this book.'))
        : t('detail.logs.run_sub', 'Showing the merged run log across the whole batch.');

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
      byId('detail_artifact_story_root').textContent = '-';
      byId('detail_artifact_book').textContent = '-';
      byId('detail_artifact_stage').textContent = '-';
      byId('detail_artifact_eval').textContent = '-';
      byId('detail_artifact_label_stage').textContent = t('detail.artifact.stage', 'Last Stage');
      byId('detail_timeline_title').textContent = t('detail.timeline.title', 'Timeline and Alerts');
      byId('detail_timeline_sub').textContent = t('detail.timeline.sub', 'Run-level events and alerts for the whole batch.');
      byId('detail_logs_title').textContent = t('detail.logs.title', 'Run Logs');
      byId('detail_logs_sub').textContent = t('detail.logs.sub', 'Select a book to inspect its captured terminal log.');
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
      const data = await apiGet('/api/capacity?window=40');
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
        const queuePromise = runCapabilityTask('queue_api', fetchQueue, null);
        const alertsPromise = runCapabilityTask('alerts_api', fetchAlerts, null);
        const capacityPromise = runCapabilityTask('capacity_api', fetchCapacity, null);
        const historyPromise = fetchHistory();
        const imagesPromise = ui.activeTab === 'modules' ? fetchImages() : Promise.resolve(null);
        const configsPromise = ui.activeTab === 'ops'
          ? runCapabilityTask('configs_api', fetchConfigVersions, null)
          : Promise.resolve(null);
        const modulesPromise = ui.activeTab === 'modules' ? fetchModuleJobs() : Promise.resolve(null);
        const galleryPromise = ui.activeTab === 'gallery' ? fetchGallery(true) : Promise.resolve(null);
        const systemPromise = pollSystemStatus(true);
        const evaluationPromise = ui.activeTab === 'evaluation' ? fetchEvaluation(false) : Promise.resolve(null);

        const results = await Promise.allSettled([
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

        const queueData = results[1] && results[1].status === 'fulfilled' ? (results[1].value || null) : null;
        const alertsData = results[2] && results[2].status === 'fulfilled' ? (results[2].value || null) : null;
        const capacityData = results[3] && results[3].status === 'fulfilled' ? (results[3].value || null) : null;
        const configsData = results[6] && results[6].status === 'fulfilled' ? (results[6].value || null) : null;
        renderQueue(queueData);
        renderAlerts(alertsData && alertsData.items ? alertsData.items : alertsData);
        renderCapacity(capacityData);
        if (ui.activeTab === 'ops') {
          renderConfigVersions(configsData && configsData.items ? configsData.items : configsData);
        }
        updateHeaderKpis(status, capacityData);
        const refreshErrors = results
          .filter(function (item) { return item && item.status === 'rejected'; })
          .map(function (item) { return String((item.reason && item.reason.message) || item.reason || 'refresh error'); })
          .filter(function (message) { return !isMissingEndpointError(message); });
        const compatibilityMessage = composeCompatibilityMessage();
        const backgroundText = refreshErrors.length ? refreshErrors[0] : compatibilityMessage;
        const backgroundTone = refreshErrors.length || compatibilityMessage ? 'warn' : '';
        setBackgroundMessage(backgroundText, backgroundTone);

        if (ui.activeTab === 'detail') {
          await fetchRunDetail();
        }
        if (ui.activeTab === 'modules' && ui.moduleSelectedJobId) {
          await fetchModuleJobDetail(ui.moduleSelectedJobId);
        }
        renderKgSummary();
        renderDemoStoryline();
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
      renderPageHeader();
      renderDemoStoryline();
      if (tabName === 'detail') {
        fetchRunDetail();
      }
      if (tabName === 'overview' || tabName === 'ops') {
        refreshOverview(true);
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
      byId('translation_enabled').addEventListener('change', syncStrictOptionAvailability);
      byId('voice_enabled').addEventListener('change', syncStrictOptionAvailability);
      byId('model_plan').addEventListener('change', function () {
        renderModelPlanStatus(ui.lastSystemStatus);
        renderDashboardHealth(ui.lastSystemStatus, ui.latestStatus);
        renderKgSummary();
      });
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
          if (ui.evaluation.branch.toLowerCase() !== 'canonical') {
            ui.evaluation.showAdvanced = true;
          }
          syncEvaluationAdvancedControls();
          if (ui.activeTab === 'evaluation') {
            fetchEvaluation(true);
          }
        });
      }
      const evalAdvancedBtn = byId('btn_eval_advanced');
      if (evalAdvancedBtn) {
        evalAdvancedBtn.addEventListener('click', function () {
          ui.evaluation.showAdvanced = !ui.evaluation.showAdvanced;
          syncEvaluationAdvancedControls();
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
      byId('btn_module_trans_target_recommended').addEventListener('click', function () {
        setTranslationTargetSelection('recommended');
      });
      byId('btn_module_trans_target_all').addEventListener('click', function () {
        setTranslationTargetSelection('all');
      });
      byId('btn_module_trans_target_none').addEventListener('click', function () {
        setTranslationTargetSelection('none');
      });
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
      [
        'age',
        'category',
        'theme',
        'subcategory',
        'theme_custom',
        'subcategory_custom',
        'story_prompt',
        'story_materials',
        'photo_enabled',
        'translation_enabled',
        'voice_enabled',
        'verify_enabled',
        'model_plan'
      ].forEach(function (id) {
        const node = byId(id);
        if (!node) return;
        node.addEventListener('change', renderKgSummary);
        if (node.tagName === 'INPUT' || node.tagName === 'TEXTAREA') {
          node.addEventListener('input', renderKgSummary);
        }
      });
      byId('btn_speaker_mode_preset').addEventListener('click', function () {
        setSpeakerSourceMode('preset');
        syncSpeakerSelection();
      });
      byId('btn_speaker_mode_custom').addEventListener('click', function () {
        setSpeakerSourceMode('custom');
        refreshOverviewSpeakerLibraries({
          dir: (byId('speaker_dir') && byId('speaker_dir').value) ? byId('speaker_dir').value : '',
          wav: (byId('speaker_wav') && byId('speaker_wav').value) ? byId('speaker_wav').value : '',
        });
      });
      byId('speaker_custom_wav_select').addEventListener('change', syncSpeakerSelection);
      byId('speaker_dir').addEventListener('change', function () {
        refreshOverviewSpeakerLibraries({
          dir: (byId('speaker_dir') && byId('speaker_dir').value) ? byId('speaker_dir').value : '',
          wav: '',
        });
      });
      byId('btn_refresh_preset_speakers').addEventListener('click', function () {
        refreshOverviewSpeakerLibraries({
          dir: (byId('speaker_dir') && byId('speaker_dir').value) ? byId('speaker_dir').value : '',
          wav: (byId('speaker_wav') && byId('speaker_wav').value) ? byId('speaker_wav').value : '',
        });
      });
      byId('btn_refresh_custom_speakers').addEventListener('click', function () {
        refreshOverviewSpeakerLibraries({
          dir: (byId('speaker_dir') && byId('speaker_dir').value) ? byId('speaker_dir').value : '',
          wav: (byId('speaker_wav') && byId('speaker_wav').value) ? byId('speaker_wav').value : '',
        });
      });
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

      const demoJumpButtons = document.querySelectorAll('[data-target-tab]');
      demoJumpButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
          const targetTab = String(btn.getAttribute('data-target-tab') || 'overview');
          switchTab(targetTab);
        });
      });

      const moduleTabButtons = document.querySelectorAll('.module-tab-btn');
      moduleTabButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
          switchModuleStudio(String(btn.getAttribute('data-module-tab') || 'story'));
        });
      });

      const moduleJumpButtons = document.querySelectorAll('[data-module-tab-jump]');
      moduleJumpButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
          switchModuleStudio(String(btn.getAttribute('data-module-tab-jump') || 'story'));
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
        renderGallerySnapshot(data);
        const images = Array.isArray(data && data.images) ? data.images : [];
        if (!images.length) {
          cont.innerHTML = renderGalleryEmptyState();
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
          cont.innerHTML = renderGalleryEmptyState();
          renderGallerySnapshot({images: []});
          return null;
        }
      }

      async function pollSystemStatus(force) {
        try {
          const data = await apiGet('/api/system');
          ui.lastSystemStatus = data;
          syncCapabilitiesFromPayload(data);
          renderModelPlanStatus(data);
          renderSystemTelemetry(data);
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
      setSpeakerSourceMode(currentSpeakerSourceMode());
      syncStoryInputMode();
      syncModuleStoryInputMode();
      fetchTemplates();
      pollSystemStatus(true);
      switchModuleStudio('story');
      loadHiddenModuleJobs();
      bindEvents();
      syncEvaluationSourceControls();
      syncEvaluationAdvancedControls();
      updateEvaluationRunSelect();
      syncTranslationSourceLangByFolder();
      fetchTranslatableStories();
      refreshOverviewSpeakerLibraries({
        dir: (byId('speaker_dir') && byId('speaker_dir').value) ? byId('speaker_dir').value : '',
        wav: (byId('speaker_wav') && byId('speaker_wav').value) ? byId('speaker_wav').value : '',
      });
      restartTimer();
      refreshOverview(true);
      if (ui.activeTab === 'gallery') {
        fetchGallery(true);
      }
    }

    init();
