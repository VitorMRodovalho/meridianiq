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
		{ id: 'api', title: 'API Reference' },
	];
</script>

<svelte:head>
	<title>Documentation - MeridianIQ</title>
</svelte:head>

<div class="flex">
	<!-- Docs sidebar -->
	<nav class="w-56 shrink-0 border-r border-gray-200 p-6 hidden lg:block sticky top-0 h-screen overflow-y-auto">
		<p class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-4">Documentation</p>
		{#each sections as section}
			<button
				onclick={() => activeSection = section.id}
				class="block w-full text-left px-3 py-1.5 rounded-md text-sm mb-0.5 transition-colors {activeSection === section.id
					? 'bg-blue-50 text-blue-700 font-medium'
					: 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}"
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
				<span class="text-sm font-medium text-gray-700">Section</span>
				<select bind:value={activeSection} class="mt-1 block w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
					{#each sections as section}
						<option value={section.id}>{section.title}</option>
					{/each}
				</select>
			</label>
		</div>

		{#if activeSection === 'getting-started'}
			<h1 class="text-2xl font-bold text-gray-900 mb-4">Getting Started</h1>
			<p class="text-gray-600 mb-4">MeridianIQ analyzes Primavera P6 schedule exports (XER format). Here's the typical workflow:</p>
			<ol class="list-decimal list-inside space-y-3 text-gray-600 mb-6">
				<li><strong>Export from P6:</strong> In Primavera P6, go to File > Export > XER. Select the project and export.</li>
				<li><strong>Upload:</strong> Navigate to Upload and drag your .xer file into the upload zone.</li>
				<li><strong>Analyze:</strong> MeridianIQ automatically parses the file and runs DCMA validation, CPM analysis, and health scoring.</li>
				<li><strong>Compare:</strong> Upload a second version of the same schedule to unlock comparison, forensic delay analysis, and float trend tracking.</li>
				<li><strong>Report:</strong> Generate PDF reports from any project detail page using the "Generate Report" button.</li>
			</ol>
			<div class="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
				<strong>Tip:</strong> For the best experience, upload at least 2 consecutive schedule updates from the same project. This enables comparison, forensic analysis, and float trend tracking.
			</div>

		{:else if activeSection === 'upload'}
			<h1 class="text-2xl font-bold text-gray-900 mb-4">Uploading Schedules</h1>
			<p class="text-gray-600 mb-4">MeridianIQ supports Oracle Primavera P6 XER files (version 7.0 and later).</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Supported Data</h2>
			<p class="text-gray-600 mb-2">The parser extracts 17+ table types from the XER format:</p>
			<ul class="list-disc list-inside space-y-1 text-gray-600 text-sm mb-4">
				<li>PROJECT — Project metadata and data date</li>
				<li>PROJWBS — Work Breakdown Structure hierarchy</li>
				<li>TASK — Activities with dates, durations, status</li>
				<li>TASKPRED — Predecessor relationships with types and lags</li>
				<li>TASKRSRC — Resource assignments with costs</li>
				<li>CALENDAR — Work calendars with exceptions</li>
				<li>RSRC — Resource definitions</li>
			</ul>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Encoding</h2>
			<p class="text-gray-600">The parser auto-detects encoding (UTF-8, Windows-1252, Latin-1). No manual configuration needed.</p>

		{:else if activeSection === 'dcma'}
			<h1 class="text-2xl font-bold text-gray-900 mb-4">DCMA 14-Point Assessment</h1>
			<p class="text-gray-600 mb-4">The DCMA (Defense Contract Management Agency) 14-Point Assessment evaluates schedule quality across 14 standardized metrics.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Checks</h2>
			<div class="overflow-x-auto">
				<table class="min-w-full text-sm divide-y divide-gray-200">
					<thead class="bg-gray-50">
						<tr>
							<th class="px-3 py-2 text-left text-xs font-medium text-gray-500">#</th>
							<th class="px-3 py-2 text-left text-xs font-medium text-gray-500">Check</th>
							<th class="px-3 py-2 text-left text-xs font-medium text-gray-500">Threshold</th>
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
							<tr class="hover:bg-gray-50">
								<td class="px-3 py-2 text-gray-500">{num}</td>
								<td class="px-3 py-2 text-gray-900">{name}</td>
								<td class="px-3 py-2 font-mono text-gray-600">{threshold}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

		{:else if activeSection === 'compare'}
			<h1 class="text-2xl font-bold text-gray-900 mb-4">Schedule Comparison</h1>
			<p class="text-gray-600 mb-4">Compare two versions of a schedule to detect changes, additions, deletions, and potential manipulation.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Matching Algorithm</h2>
			<p class="text-gray-600 mb-2">Multi-layer matching ensures accurate activity pairing:</p>
			<ol class="list-decimal list-inside space-y-1 text-gray-600 text-sm">
				<li><strong>Tier 1:</strong> Match by task_id (guaranteed unique within a P6 database)</li>
				<li><strong>Tier 2:</strong> Match by task_code (user-assigned activity code)</li>
				<li><strong>Unmatched:</strong> Classified as truly added or deleted</li>
			</ol>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Manipulation Detection</h2>
			<p class="text-gray-600">Six indicators flag potential schedule manipulation: retroactive dates, out-of-sequence progress, constraint masking, duration changes, logic changes, and code restructuring.</p>

		{:else if activeSection === 'forensic'}
			<h1 class="text-2xl font-bold text-gray-900 mb-4">Forensic Analysis (CPA)</h1>
			<p class="text-gray-600 mb-4">Contemporaneous Period Analysis per AACE Recommended Practice 29R-03. Analyzes schedule evolution across multiple update periods.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">How It Works</h2>
			<ol class="list-decimal list-inside space-y-1 text-gray-600 text-sm">
				<li>Upload 3+ consecutive schedule updates</li>
				<li>Create a forensic timeline from the project list</li>
				<li>Each consecutive pair forms an "analysis window"</li>
				<li>Per window: completion date delta, critical path evolution, driving activity</li>
				<li>Results displayed as a delay waterfall chart</li>
			</ol>

		{:else if activeSection === 'tia'}
			<h1 class="text-2xl font-bold text-gray-900 mb-4">Time Impact Analysis</h1>
			<p class="text-gray-600 mb-4">Per AACE Recommended Practice 52R-06. Measures the impact of delay events on the project completion date.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Workflow</h2>
			<ol class="list-decimal list-inside space-y-1 text-gray-600 text-sm">
				<li>Select a base schedule</li>
				<li>Define delay fragments (activities, durations, predecessor/successor links)</li>
				<li>Assign responsible party (Owner, Contractor, Shared, Third Party, Force Majeure)</li>
				<li>Run analysis — MeridianIQ inserts fragments into the network and re-runs CPM</li>
				<li>Compare impacted vs unimpacted completion to quantify delay</li>
			</ol>

		{:else if activeSection === 'evm'}
			<h1 class="text-2xl font-bold text-gray-900 mb-4">Earned Value Management</h1>
			<p class="text-gray-600 mb-4">Per ANSI/EIA-748. Computes cost and schedule performance indices from resource-loaded schedules.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Key Metrics</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 text-sm">
				<li><strong>SPI</strong> — Schedule Performance Index (EV / PV)</li>
				<li><strong>CPI</strong> — Cost Performance Index (EV / AC)</li>
				<li><strong>EAC</strong> — Estimate at Completion (multiple scenarios)</li>
				<li><strong>TCPI</strong> — To-Complete Performance Index</li>
				<li><strong>S-Curve</strong> — Time-phased PV, EV, AC visualization</li>
			</ul>

		{:else if activeSection === 'risk'}
			<h1 class="text-2xl font-bold text-gray-900 mb-4">Monte Carlo Risk Simulation</h1>
			<p class="text-gray-600 mb-4">Quantitative Schedule Risk Analysis (QSRA) per AACE Recommended Practice 57R-09.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Process</h2>
			<ol class="list-decimal list-inside space-y-1 text-gray-600 text-sm">
				<li>Assign uncertainty ranges (min / most likely / max) to activity durations</li>
				<li>Run 1,000 iterations — each samples from PERT-Beta distributions</li>
				<li>CPM recalculated each iteration</li>
				<li>Results: completion probability distribution (P10, P50, P80, P90)</li>
				<li>Tornado diagram shows sensitivity (Spearman rank correlation)</li>
				<li>Criticality index shows % of iterations each activity was on the critical path</li>
			</ol>

		{:else if activeSection === 'health'}
			<h1 class="text-2xl font-bold text-gray-900 mb-4">Health Score & Early Warning</h1>
			<p class="text-gray-600 mb-4">Composite 0-100 metric combining multiple indicators for at-a-glance schedule health assessment.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Score Components</h2>
			<ul class="list-disc list-inside space-y-1 text-gray-600 text-sm">
				<li><strong>40%</strong> — DCMA Assessment score</li>
				<li><strong>25%</strong> — Float health (distribution, negative float %)</li>
				<li><strong>20%</strong> — Logic quality (relationship completeness)</li>
				<li><strong>15%</strong> — Trend indicators (float velocity, CP stability)</li>
			</ul>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Early Warning Rules</h2>
			<p class="text-gray-600">12 configurable rules monitor for: float erosion velocity, critical path changes, DCMA threshold breaches, near-critical drift, and more.</p>

		{:else if activeSection === 'api'}
			<h1 class="text-2xl font-bold text-gray-900 mb-4">API Reference</h1>
			<p class="text-gray-600 mb-4">MeridianIQ exposes 45 REST endpoints under <code class="bg-gray-100 px-1.5 py-0.5 rounded text-sm">/api/v1/</code>.</p>
			<h2 class="text-lg font-semibold text-gray-800 mt-6 mb-2">Interactive Documentation</h2>
			<p class="text-gray-600 mb-4">
				The FastAPI backend auto-generates OpenAPI documentation:
			</p>
			<ul class="list-disc list-inside space-y-1 text-gray-600 text-sm mb-4">
				<li><strong>Swagger UI:</strong> <code class="bg-gray-100 px-1.5 py-0.5 rounded">/docs</code></li>
				<li><strong>ReDoc:</strong> <code class="bg-gray-100 px-1.5 py-0.5 rounded">/redoc</code></li>
				<li><strong>OpenAPI JSON:</strong> <code class="bg-gray-100 px-1.5 py-0.5 rounded">/openapi.json</code></li>
			</ul>
			<p class="text-gray-600">All endpoints require Bearer token authentication (Supabase JWT). The token is automatically attached by the frontend.</p>
		{/if}
	</div>
</div>
