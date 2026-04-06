<script lang="ts">
	import { page } from '$app/stores';

	const routeLabels: Record<string, string> = {
		'': 'Dashboard',
		'projects': 'Projects',
		'upload': 'Upload',
		'compare': 'Compare',
		'forensic': 'Forensic',
		'tia': 'TIA',
		'contract': 'Contract',
		'evm': 'EVM',
		'risk': 'Risk',
		'risk-register': 'Risk Register',
		'scorecard': 'Scorecard',
		'whatif': 'What-If',
		'resources': 'Resources',
		'builder': 'Schedule Builder',
		'visualization': '4D Visualization',
		'anomalies': 'Anomalies',
		'root-cause': 'Root Cause',
		'delay-prediction': 'Delay Prediction',
		'duration-prediction': 'Duration ML',
		'delay-attribution': 'Delay Attribution',
		'benchmarks': 'Benchmarks',
		'float-trends': 'Float Trends',
		'reports': 'Reports',
		'optimizer': 'Optimizer',
		'calendar-validation': 'Calendars',
		'lookahead': 'Look-Ahead',
		'cashflow': 'Cash Flow',
		'ips': 'IPS Reconcile',
		'recovery': 'Recovery',
		'milestones': 'Milestones',
		'org': 'Organizations',
		'settings': 'Settings',
		'docs': 'Documentation',
		'demo': 'Demo',
		'programs': 'Programs',
		'login': 'Sign In',
	};

	const crumbs = $derived.by(() => {
		const pathname = $page.url.pathname;
		if (pathname === '/') return [];

		const segments = pathname.split('/').filter(Boolean);
		const result: { label: string; href: string }[] = [{ label: 'Dashboard', href: '/' }];

		let path = '';
		for (const seg of segments) {
			path += `/${seg}`;
			const label = routeLabels[seg] || seg.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
			result.push({ label, href: path });
		}

		return result;
	});
</script>

{#if crumbs.length > 1}
	<nav class="px-4 py-2 text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1 overflow-x-auto" aria-label="Breadcrumb">
		{#each crumbs as crumb, i}
			{#if i > 0}
				<svg class="w-3 h-3 text-gray-300 dark:text-gray-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
				</svg>
			{/if}
			{#if i === crumbs.length - 1}
				<span class="text-gray-900 dark:text-gray-100 font-medium truncate">{crumb.label}</span>
			{:else}
				<a href={crumb.href} class="hover:text-blue-600 dark:hover:text-blue-400 transition-colors truncate">{crumb.label}</a>
			{/if}
		{/each}
	</nav>
{/if}
