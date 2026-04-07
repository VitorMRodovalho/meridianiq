<script lang="ts">
	let activeSection = $state('getting-started');

	const sections = [
		{ id: 'getting-started', title: 'Getting Started' },
		{ id: 'upload', title: 'Uploading Schedules' },
		{ id: 'dcma', title: 'DCMA 14-Point Assessment' },
		{ id: 'compare', title: 'Schedule Comparison' },
		{ id: 'forensic', title: 'Forensic Analysis (CPA)' },
		{ id: 'tia', title: 'Time Impact Analysis' },
		{ id: 'evm', title: 'Earned Value Management' },
		{ id: 'risk', title: 'Monte Carlo Simulation' },
		{ id: 'health', title: 'Health Score & Alerts' },
		{ id: 'anomalies', title: 'Anomaly Detection' },
		{ id: 'rootcause', title: 'Root Cause Analysis' },
		{ id: 'floattrends', title: 'Float Trends & Entropy' },
		{ id: 'scorecard', title: 'Schedule Scorecard' },
		{ id: 'whatif', title: 'What-If Simulator' },
		{ id: 'resources', title: 'Resource Leveling' },
		{ id: 'builder', title: 'Schedule Builder' },
		{ id: 'benchmarks', title: 'Benchmarks & Percentiles' },
		{ id: 'delay', title: 'Delay & Duration Prediction' },
		{ id: 'pareto', title: 'Pareto Trade-Off Analysis' },
		{ id: 'visualization', title: '4D Visualization' },
		{ id: 'schedule', title: 'Schedule Viewer' },
		{ id: 'optimizer', title: 'Schedule Optimizer' },
		{ id: 'reports', title: 'Reports Hub' },
		{ id: 'export', title: 'XER Export' },
		{ id: 'mcp', title: 'MCP & AI Integration' },
		{ id: 'api', title: 'API Reference' },
	];
</script>

<svelte:head>
	<title>Documentation - MeridianIQ</title>
</svelte:head>

<div class="flex">
	<!-- Docs sidebar -->
	<nav class="w-56 shrink-0 border-r border-gray-200 dark:border-gray-700 p-6 hidden lg:block sticky top-0 h-screen overflow-y-auto">
		<p class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-4">Documentation</p>
		{#each sections as section}
			<button
				onclick={() => activeSection = section.id}
				class="block w-full text-left px-3 py-1.5 rounded-md text-sm mb-0.5 transition-colors {activeSection === section.id
					? 'bg-blue-50 dark:bg-blue-950 text-blue-700 font-medium'
					: 'text-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:text-gray-100'}"
			>
				{section.title}
			</button>
		{/each}
	</nav>

	<!-- Content -->
	<div class="flex-1 p-8 max-w-4xl">
		<!-- Mobile section selector -->
		<div class="lg:hidden mb-6">
			<label class="block">
				<span class="text-sm font-medium text-gray-700 dark:text-gray-300">Section</span>
				<select bind:value={activeSection} class="mt-1 block w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm">
					{#each sections as section}
						<option value={section.id}>{section.title}</option>
					{/each}
				</select>
			</label>
		</div>

		{#if activeSection === 'getting-started'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Getting Started</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">MeridianIQ analyzes Primavera P6 schedule exports (XER format). Here's the typical workflow:</p>
			<ol class="list-decimal list-inside space-y-3 text-gray-600 dark:text-gray-400 mb-6">
				<li><strong>Export from P6:</strong> In Primavera P6, go to File > Export > XER. Select the project and export.</li>
				<li><strong>Upload:</strong> Navigate to Upload and drag your .xer file into the upload zone.</li>
				<li><strong>Analyze:</strong> MeridianIQ automatically parses the file and runs DCMA validation, CPM analysis, and health scoring.</li>
				<li><strong>Compare:</strong> Upload a second version of the same schedule to unlock comparison, forensic delay analysis, and float trend tracking.</li>
				<li><strong>Report:</strong> Generate PDF reports from any project detail page using the "Generate Report" button.</li>
			</ol>
			<div class="bg-blue-50 dark:bg-blue-950 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
				<strong>Tip:</strong> For the best experience, upload at least 2 consecutive schedule updates from the same project. This enables comparison, forensic analysis, and float trend tracking.
			</div>

		{:else if activeSection === 'upload'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Uploading Schedules</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">MeridianIQ supports Oracle Primavera P6 XER files (version 7.0 and later).</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Supported Data</h2>
			<p class="text-gray-600 dark:text-gray-400 mb-2">The parser extracts 17+ table types from the XER format:</p>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm mb-4">
				<li>PROJECT — Project metadata and data date</li>
				<li>PROJWBS — Work Breakdown Structure hierarchy</li>
				<li>TASK — Activities with dates, durations, status</li>
				<li>TASKPRED — Predecessor relationships with types and lags</li>
				<li>TASKRSRC — Resource assignments with costs</li>
				<li>CALENDAR — Work calendars with exceptions</li>
				<li>RSRC — Resource definitions</li>
			</ul>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Encoding</h2>
			<p class="text-gray-600 dark:text-gray-400">The parser auto-detects encoding (UTF-8, Windows-1252, Latin-1). No manual configuration needed.</p>

		{:else if activeSection === 'dcma'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">DCMA 14-Point Assessment</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">The DCMA (Defense Contract Management Agency) 14-Point Assessment evaluates schedule quality across 14 standardized metrics.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Checks</h2>
			<div class="overflow-x-auto">
				<table class="min-w-full text-sm divide-y divide-gray-200">
					<thead class="bg-gray-50 dark:bg-gray-800">
						<tr>
							<th class="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">#</th>
							<th class="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Check</th>
							<th class="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Threshold</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200">
						{#each [
							['1', 'Logic (predecessors + successors)', '>= 90%'],
							['2', 'Leads (negative lags)', '<= 0%'],
							['3', 'Lags (positive lags)', '<= 5%'],
							['4', 'Relationship Types (FS)', '>= 90%'],
							['5', 'Hard Constraints', '<= 5%'],
							['6', 'High Float (> 44 days)', '<= 5%'],
							['7', 'Negative Float', '<= 0%'],
							['8', 'High Duration (> 44 days)', '<= 5%'],
							['9', 'Invalid Dates', '<= 0%'],
							['10', 'Resources', '>= 90%'],
							['11', 'Missed Tasks', '<= 5%'],
							['12', 'Critical Path Test', 'Pass/Fail'],
							['13', 'CPLI', '>= 0.95'],
							['14', 'BEI', '>= 0.95'],
						] as [num, name, threshold]}
							<tr class="hover:bg-gray-50 dark:hover:bg-gray-800">
								<td class="px-3 py-2 text-gray-500 dark:text-gray-400">{num}</td>
								<td class="px-3 py-2 text-gray-900 dark:text-gray-100">{name}</td>
								<td class="px-3 py-2 font-mono text-gray-600 dark:text-gray-400">{threshold}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

		{:else if activeSection === 'compare'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Schedule Comparison</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Compare two versions of a schedule to detect changes, additions, deletions, and potential manipulation.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Matching Algorithm</h2>
			<p class="text-gray-600 dark:text-gray-400 mb-2">Multi-layer matching ensures accurate activity pairing:</p>
			<ol class="list-decimal list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>Tier 1:</strong> Match by task_id (guaranteed unique within a P6 database)</li>
				<li><strong>Tier 2:</strong> Match by task_code (user-assigned activity code)</li>
				<li><strong>Unmatched:</strong> Classified as truly added or deleted</li>
			</ol>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Manipulation Detection</h2>
			<p class="text-gray-600 dark:text-gray-400">Six indicators flag potential schedule manipulation: retroactive dates, out-of-sequence progress, constraint masking, duration changes, logic changes, and code restructuring.</p>

		{:else if activeSection === 'forensic'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Forensic Analysis (CPA)</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Contemporaneous Period Analysis per AACE Recommended Practice 29R-03. Analyzes schedule evolution across multiple update periods.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">How It Works</h2>
			<ol class="list-decimal list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li>Upload 3+ consecutive schedule updates</li>
				<li>Create a forensic timeline from the project list</li>
				<li>Each consecutive pair forms an "analysis window"</li>
				<li>Per window: completion date delta, critical path evolution, driving activity</li>
				<li>Results displayed as a delay waterfall chart</li>
			</ol>

		{:else if activeSection === 'tia'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Time Impact Analysis</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Per AACE Recommended Practice 52R-06. Measures the impact of delay events on the project completion date.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Workflow</h2>
			<ol class="list-decimal list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li>Select a base schedule</li>
				<li>Define delay fragments (activities, durations, predecessor/successor links)</li>
				<li>Assign responsible party (Owner, Contractor, Shared, Third Party, Force Majeure)</li>
				<li>Run analysis — MeridianIQ inserts fragments into the network and re-runs CPM</li>
				<li>Compare impacted vs unimpacted completion to quantify delay</li>
			</ol>

		{:else if activeSection === 'evm'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Earned Value Management</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Per ANSI/EIA-748. Computes cost and schedule performance indices from resource-loaded schedules.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Key Metrics</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>SPI</strong> — Schedule Performance Index (EV / PV)</li>
				<li><strong>CPI</strong> — Cost Performance Index (EV / AC)</li>
				<li><strong>EAC</strong> — Estimate at Completion (multiple scenarios)</li>
				<li><strong>TCPI</strong> — To-Complete Performance Index</li>
				<li><strong>S-Curve</strong> — Time-phased PV, EV, AC visualization</li>
			</ul>

		{:else if activeSection === 'risk'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Monte Carlo Risk Simulation</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Quantitative Schedule Risk Analysis (QSRA) per AACE Recommended Practice 57R-09.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Process</h2>
			<ol class="list-decimal list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li>Assign uncertainty ranges (min / most likely / max) to activity durations</li>
				<li>Run 1,000 iterations — each samples from PERT-Beta distributions</li>
				<li>CPM recalculated each iteration</li>
				<li>Results: completion probability distribution (P10, P50, P80, P90)</li>
				<li>Tornado diagram shows sensitivity (Spearman rank correlation)</li>
				<li>Criticality index shows % of iterations each activity was on the critical path</li>
			</ol>

		{:else if activeSection === 'health'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Health Score & Early Warning</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Composite 0-100 metric combining multiple indicators for at-a-glance schedule health assessment.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Score Components</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>40%</strong> — DCMA Assessment score</li>
				<li><strong>25%</strong> — Float health (distribution, negative float %)</li>
				<li><strong>20%</strong> — Logic quality (relationship completeness)</li>
				<li><strong>15%</strong> — Trend indicators (float velocity, CP stability)</li>
			</ul>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Early Warning Rules</h2>
			<p class="text-gray-600 dark:text-gray-400">12 configurable rules monitor for: float erosion velocity, critical path changes, DCMA threshold breaches, near-critical drift, and more.</p>

		{:else if activeSection === 'anomalies'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Anomaly Detection</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Statistical outlier detection using IQR (Interquartile Range) and z-score methods to flag activities with unusual characteristics.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Detection Methods</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>Duration anomalies</strong> — Activities with unusually long or short durations</li>
				<li><strong>Float anomalies</strong> — Extreme positive or negative total float values</li>
				<li><strong>Progress anomalies</strong> — Physical progress inconsistent with schedule dates</li>
				<li><strong>Relationship anomalies</strong> — Unusual predecessor/successor counts</li>
			</ul>
			<p class="text-gray-600 dark:text-gray-400 mt-4">Navigate to <strong>/anomalies</strong> to scan a project. Results include severity levels (high/medium/low) and z-scores for each anomaly.</p>

		{:else if activeSection === 'rootcause'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Root Cause Analysis</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Backwards network trace through the dependency graph to identify the originating delay event driving the project completion date.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">How It Works</h2>
			<ol class="list-decimal list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li>Start from a target activity (or auto-detect the project completion driver)</li>
				<li>Walk backwards through driving predecessors using NetworkX</li>
				<li>At each step, select the predecessor with the latest early finish (the "driver")</li>
				<li>Continue until reaching an activity with no predecessors (the root cause)</li>
			</ol>
			<p class="text-gray-600 dark:text-gray-400 mt-4">Navigate to <strong>/root-cause</strong> and optionally specify a target activity ID. The result shows the full dependency chain with total float and relationship types at each step.</p>

		{:else if activeSection === 'floattrends'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Float Trends & Entropy</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Two complementary metrics for assessing schedule manipulation and float health.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Shannon Entropy</h2>
			<p class="text-gray-600 dark:text-gray-400 text-sm mb-4">Measures how uniformly total float is spread across buckets. Low entropy = float concentrated in few categories (suspicious). High entropy = even distribution (healthy). No baseline required.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Constraint Accumulation</h2>
			<p class="text-gray-600 dark:text-gray-400 text-sm">Measures the rate at which hard constraints are being added between schedule versions. Excessive growth is a manipulation indicator per DCMA check #10 and AACE RP 29R-03. Requires both a baseline and update schedule.</p>

		{:else if activeSection === 'scorecard'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Schedule Scorecard</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">The scorecard aggregates 5 quality dimensions into a single letter grade (A-F) with actionable recommendations.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Dimensions</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>Validation (30%)</strong> — DCMA 14-Point overall score</li>
				<li><strong>Health (25%)</strong> — Composite float, logic, and trend health</li>
				<li><strong>Risk (20%)</strong> — Delay prediction score (inverted: low risk = high score)</li>
				<li><strong>Logic (15%)</strong> — Network completeness minus constraint usage</li>
				<li><strong>Completeness (10%)</strong> — Calendar, duration, date, and WBS assignment coverage</li>
			</ul>
			<p class="text-gray-600 dark:text-gray-400 mt-4">Navigate to <strong>/scorecard</strong> and select a project. Standards: DCMA 14-Point, GAO Schedule Guide, AACE RP 49R-06.</p>

		{:else if activeSection === 'whatif'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">What-If Simulator</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Explore schedule scenarios by adjusting activity durations and re-running CPM analysis.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Modes</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>Deterministic</strong> — Apply a fixed % change, get exact duration impact</li>
				<li><strong>Probabilistic</strong> — Sample from a range, run N iterations, get P-values (P10, P50, P80, P90)</li>
			</ul>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Targeting</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">*</code> — All non-complete activities</li>
				<li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">B</code> — Specific task code</li>
				<li><code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">WBS:1.2</code> — All activities under WBS prefix</li>
			</ul>
			<p class="text-gray-600 dark:text-gray-400 mt-4">Standards: AACE RP 57R-09, PMI PMBOK 7 S4.6.</p>

		{:else if activeSection === 'resources'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Resource Leveling</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Solves the Resource-Constrained Project Scheduling Problem (RCPSP) using Serial Schedule Generation Scheme (SGS).</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Priority Rules</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>Late Start</strong> — Schedule activities with latest LS first (preserves float)</li>
				<li><strong>Early Start</strong> — Earliest available first</li>
				<li><strong>Float</strong> — Lowest total float first (protect critical activities)</li>
				<li><strong>Duration</strong> — Longest duration first</li>
			</ul>
			<p class="text-gray-600 dark:text-gray-400 mt-4">The output includes resource demand profiles over time and per-activity shifts. Standards: AACE RP 46R-11, Kolisch (1996).</p>

		{:else if activeSection === 'builder'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Schedule Builder</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Generate complete schedules from project parameters using WBS templates and stochastic duration estimation.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Project Types</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>Commercial</strong> — Office, retail, healthcare (7 WBS phases)</li>
				<li><strong>Industrial</strong> — Plant, refinery, data center (8 WBS phases)</li>
				<li><strong>Infrastructure</strong> — Road, bridge, tunnel (6 WBS phases)</li>
				<li><strong>Residential</strong> — Housing, apartment (7 WBS phases)</li>
			</ul>
			<p class="text-gray-600 dark:text-gray-400 mt-4">Size categories: small (&lt;100), medium (100-500), large (500-2000), mega (&gt;2000). Generated schedules are fully compatible with all analysis engines.</p>

		{:else if activeSection === 'benchmarks'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Benchmarks & Percentiles</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Compare your schedule against 100 anonymized benchmark projects to understand where you stand in the industry.</p>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li>Percentile ranking for 20+ metrics (DCMA score, float distribution, logic density)</li>
				<li>Filtered by size category (small, medium, large, mega)</li>
				<li>No identifying information stored — fully anonymized</li>
			</ul>

		{:else if activeSection === 'delay'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Delay & Duration Prediction</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">ML-powered prediction using Random Forest + Gradient Boosting ensemble models.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Delay Prediction</h2>
			<p class="text-gray-600 dark:text-gray-400 text-sm">Per-activity risk scoring (0-100) with explainable risk factors. 30 features including float, logic, duration, network, progress, and trend. Rule-based or ML mode via <code class="bg-gray-100 dark:bg-gray-800 px-1 rounded">?model=ml</code> parameter.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Duration Prediction</h2>
			<p class="text-gray-600 dark:text-gray-400 text-sm">Project-level duration forecast trained on benchmark database. Returns predicted duration with confidence intervals (P20-P80 from RF tree variance).</p>

		{:else if activeSection === 'pareto'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Pareto Trade-Off Analysis</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Run multiple what-if scenarios with associated costs to identify the Pareto-optimal frontier — scenarios where no other option is both cheaper and shorter.</p>
			<p class="text-gray-600 dark:text-gray-400 text-sm">Standards: AACE RP 36R-06 (Cost Classification), Kelley & Walker (1959) CPM Time-Cost Extension.</p>

		{:else if activeSection === 'visualization'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">4D Visualization</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Activities positioned by WBS group (Y-axis) and CPM dates (X-axis), color-coded by status:</p>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><span class="text-red-500 font-bold">Red</span> — Critical path</li>
				<li><span class="text-blue-500 font-bold">Blue</span> — Active (in progress)</li>
				<li><span class="text-green-500 font-bold">Green</span> — Complete</li>
				<li><span class="text-gray-400 font-bold">Gray</span> — Not started</li>
				<li><span class="text-purple-400 font-bold">Purple</span> — High float (&gt;44 days)</li>
			</ul>

		{:else if activeSection === 'schedule'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Schedule Viewer</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Interactive Gantt chart for P6 schedules with WBS hierarchy, baseline comparison, float visualization, and dependency lines.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Features</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>WBS Tree</strong> — Collapsible work breakdown structure with activity counts</li>
				<li><strong>Gantt Bars</strong> — Color-coded by status (critical, active, complete, not started)</li>
				<li><strong>Progress Overlay</strong> — Physical % complete as filled portion of bar</li>
				<li><strong>Milestones</strong> — Diamond shapes for finish milestones</li>
				<li><strong>Date Axis</strong> — Day/Week/Month zoom levels with data date marker</li>
				<li><strong>Baseline Bars</strong> — Gray dashed bars below current bars showing planned dates</li>
				<li><strong>Float Bars</strong> — Amber bars extending from early finish to late finish</li>
				<li><strong>Sliding Right</strong> — Amber arrow indicator for delayed activities</li>
				<li><strong>Dependency Lines</strong> — SVG bezier curves (FS/FF/SS/SF) with arrow heads</li>
				<li><strong>Critical Path Filter</strong> — Toggle to show only critical activities</li>
				<li><strong>Search</strong> — Filter activities by name, code, or ID</li>
				<li><strong>Activity Table</strong> — Collapsible tabular view with 11 columns</li>
			</ul>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Usage</h2>
			<p class="text-gray-600 dark:text-gray-400 text-sm">Navigate to <strong>/schedule</strong>, select a project, optionally select a baseline for comparison, and click "View Schedule". Use the toolbar to zoom, search, toggle overlays, and expand/collapse the WBS hierarchy.</p>

		{:else if activeSection === 'optimizer'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Schedule Optimizer</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Uses Evolution Strategies (ES) to optimize resource-constrained schedules by evolving priority rules and resource allocation to minimize makespan.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Parameters</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>Generations</strong> — Number of evolutionary generations (default: 50)</li>
				<li><strong>Population</strong> — Population size per generation (default: 20)</li>
			</ul>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Output</h2>
			<p class="text-gray-600 dark:text-gray-400 text-sm">Original vs optimized makespan, improvement percentage, convergence curve, best priority rule, and per-activity shifts. Standards: Loncar (2023), Beyer & Schwefel (2002), Kolisch (1996).</p>

		{:else if activeSection === 'reports'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">Reports Hub</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Generate and download PDF reports for your project. Available report types:</p>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li><strong>Validation</strong> — DCMA 14-Point assessment with traffic lights</li>
				<li><strong>Baseline Review</strong> — Baseline schedule quality analysis</li>
				<li><strong>Forensic</strong> — CPA delay analysis with waterfall charts</li>
				<li><strong>EVM</strong> — Earned Value metrics and S-Curves</li>
				<li><strong>Monthly Review</strong> — Period-over-period progress update</li>
				<li><strong>Risk</strong> — Monte Carlo simulation results with P-values</li>
				<li><strong>Executive Summary</strong> — One-page overview for leadership</li>
			</ul>
			<p class="text-gray-600 dark:text-gray-400 mt-4">Navigate to <strong>/reports</strong>, select a project, and click "Check Reports" to see which types have sufficient data. Reports are generated as PDFs using WeasyPrint.</p>

		{:else if activeSection === 'export'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">XER Export</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">Export schedules back to Oracle P6 XER format with round-trip fidelity. Supports exporting:</p>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
				<li>Original uploaded schedules</li>
				<li>Modified schedules (post what-if or post-leveling)</li>
				<li>Generated schedules (from Schedule Builder)</li>
			</ul>
			<p class="text-gray-600 dark:text-gray-400 mt-4">Also available: Excel (.xlsx), CSV, and JSON export formats.</p>

		{:else if activeSection === 'mcp'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">MCP & AI Integration</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">MeridianIQ exposes 19 tools via the Model Context Protocol (MCP) for AI assistant integration.</p>
			<p class="text-gray-600 dark:text-gray-400 text-sm mb-4">Configure in Claude Code settings:</p>
			<pre class="bg-gray-100 dark:bg-gray-800 rounded-lg p-4 text-xs overflow-x-auto mb-4">{`{
  "mcpServers": {
    "meridianiq": {
      "command": "python",
      "args": ["-m", "src.mcp_server"]
    }
  }
}`}</pre>
			<p class="text-gray-600 dark:text-gray-400 text-sm">Tools include: upload, DCMA, CPM, health, entropy, root cause, compare, predict delays, benchmarks, half-step, what-if, scorecard, resource leveling, schedule generation, NLP builder, XER export, and ES optimization.</p>

		{:else if activeSection === 'api'}
			<h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-4">API Reference</h1>
			<p class="text-gray-600 dark:text-gray-400 mb-4">MeridianIQ exposes 77 REST endpoints under <code class="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded text-sm">/api/v1/</code>.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Interactive Documentation</h2>
			<p class="text-gray-600 dark:text-gray-400 mb-4">
				The FastAPI backend auto-generates OpenAPI documentation:
			</p>
			<ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm mb-4">
				<li><strong>Swagger UI:</strong> <code class="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">/docs</code></li>
				<li><strong>ReDoc:</strong> <code class="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">/redoc</code></li>
				<li><strong>OpenAPI JSON:</strong> <code class="bg-gray-100 dark:bg-gray-800 px-1.5 py-0.5 rounded">/openapi.json</code></li>
			</ul>
			<p class="text-gray-600 dark:text-gray-400">All endpoints require Bearer token authentication (Supabase JWT). The token is automatically attached by the frontend.</p>
		{/if}
	</div>
</div>
