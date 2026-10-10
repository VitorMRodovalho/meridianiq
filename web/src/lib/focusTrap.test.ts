import { afterEach, describe, expect, it } from 'vitest';
import { trapFocus } from './focusTrap';

function dialog(): { node: HTMLElement; title: HTMLElement; a: HTMLElement; b: HTMLElement } {
	document.body.innerHTML = `
		<button id="outside">outside</button>
		<div role="dialog">
			<h2 id="title" tabindex="-1">Title</h2>
			<input id="a" />
			<button id="off" disabled>off</button>
			<button id="b">b</button>
		</div>`;
	const node = document.querySelector<HTMLElement>('[role=dialog]')!;
	return {
		node,
		title: document.getElementById('title')!,
		a: document.getElementById('a')!,
		b: document.getElementById('b')!
	};
}

function tab(target: HTMLElement, shiftKey = false): boolean {
	const event = new KeyboardEvent('keydown', { key: 'Tab', shiftKey, bubbles: true, cancelable: true });
	target.dispatchEvent(event);
	return event.defaultPrevented;
}

describe('trapFocus', () => {
	afterEach(() => {
		document.body.innerHTML = '';
	});

	it('wraps Tab from the last control to the first, skipping disabled ones', () => {
		const { node, a, b } = dialog();
		const trap = trapFocus(node);
		b.focus();
		expect(tab(b)).toBe(true);
		expect(document.activeElement).toBe(a);
		trap.destroy();
	});

	it('wraps Shift+Tab from the first control, and from the heading, to the last', () => {
		const { node, title, a, b } = dialog();
		const trap = trapFocus(node);
		a.focus();
		expect(tab(a, true)).toBe(true);
		expect(document.activeElement).toBe(b);
		title.focus();
		expect(tab(title, true)).toBe(true);
		expect(document.activeElement).toBe(b);
		trap.destroy();
	});

	it('leaves Tab alone between controls and from the heading', () => {
		const { node, title, a } = dialog();
		const trap = trapFocus(node);
		a.focus();
		expect(tab(a)).toBe(false);
		title.focus();
		expect(tab(title)).toBe(false);
		trap.destroy();
	});

	it('stops trapping once destroyed', () => {
		const { node, b } = dialog();
		trapFocus(node).destroy();
		b.focus();
		expect(tab(b)).toBe(false);
	});

	it('treats a radio group as one stop, the checked radio', () => {
		document.body.innerHTML = `
			<div role="dialog">
				<input type="radio" name="m" id="r1" />
				<input type="radio" name="m" id="r2" checked />
				<button id="last">last</button>
			</div>`;
		const node = document.querySelector<HTMLElement>('[role=dialog]')!;
		const r2 = document.getElementById('r2')!;
		const last = document.getElementById('last')!;
		const trap = trapFocus(node);
		r2.focus();
		expect(tab(r2, true)).toBe(true);
		expect(document.activeElement).toBe(last);
		expect(tab(last)).toBe(true);
		expect(document.activeElement).toBe(r2);
		trap.destroy();
	});

	it('skips controls inside an inert or hidden part', () => {
		document.body.innerHTML = `
			<div role="dialog">
				<button id="a">a</button>
				<div hidden><button id="h">h</button></div>
			</div>`;
		const node = document.querySelector<HTMLElement>('[role=dialog]')!;
		const a = document.getElementById('a')!;
		const trap = trapFocus(node);
		a.focus();
		expect(tab(a)).toBe(true);
		expect(document.activeElement).toBe(a);
		trap.destroy();
	});
});
