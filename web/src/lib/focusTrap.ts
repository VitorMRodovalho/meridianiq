// Keep Tab and Shift+Tab inside a modal dialog (WAI-ARIA APG, Dialog
// (Modal) pattern): from the last control Tab wraps to the first, and from
// the first (or from the dialog's own heading) Shift+Tab wraps to the last.

const FOCUSABLE =
	'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])';

function focusables(node: HTMLElement): HTMLElement[] {
	const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
		(el) =>
			!el.hasAttribute('disabled') &&
			el.getAttribute('tabindex') !== '-1' &&
			!el.closest('[inert],[hidden]') &&
			!(el instanceof HTMLInputElement && el.type === 'hidden')
	);
	// A radio group is one tab stop: its checked radio, or its first one.
	return items.filter((el) => {
		if (!(el instanceof HTMLInputElement) || el.type !== 'radio' || !el.name) return true;
		const group = items.filter(
			(o): o is HTMLInputElement =>
				o instanceof HTMLInputElement && o.type === 'radio' && o.name === el.name
		);
		const stop = group.find((o) => o.checked) ?? group[0];
		return el === stop;
	});
}

export function trapFocus(node: HTMLElement): { destroy: () => void } {
	function onKey(event: KeyboardEvent): void {
		if (event.key !== 'Tab') return;
		const items = focusables(node);
		if (items.length === 0) {
			event.preventDefault();
			return;
		}
		const first = items[0];
		const last = items[items.length - 1];
		const active = document.activeElement as HTMLElement | null;
		const inside = active !== null && items.includes(active);
		if (event.shiftKey && (!inside || active === first)) {
			event.preventDefault();
			last.focus();
		} else if (!event.shiftKey && (!inside || active === last)) {
			if (!inside && active !== null && node.contains(active)) return;
			event.preventDefault();
			first.focus();
		}
	}
	node.addEventListener('keydown', onKey);
	return { destroy: () => node.removeEventListener('keydown', onKey) };
}
