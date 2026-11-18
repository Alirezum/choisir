import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChoiceBoard from '../../../src/views/ChoiceBoard.vue'

interface BoardProps {
  item: string | null
  remaining: number
  picked: number
  serial: number
  canUndo: boolean
  undoLabel: string
  canSnooze: boolean
  snoozeLabel: string
}

const defaults: BoardProps = {
  item: null,
  remaining: 10,
  picked: 0,
  serial: 0,
  canUndo: false,
  undoLabel: 'Undo last pick (nothing to undo)',
  canSnooze: false,
  snoozeLabel: 'Snooze last pick (nothing to snooze)',
}

const mountBoard = (props: Partial<BoardProps> = {}) =>
  mount(ChoiceBoard, { props: { ...defaults, ...props } })

describe('ChoiceBoard', () => {
  it('renders the empty board with title, meta, stats, and the pick lever', () => {
    const wrapper = mountBoard()

    expect(wrapper.find('h2.sr-only').text()).toBe('No item picked yet')
    expect(wrapper.find('.board-empty-title').text()).toBe('Nothing picked yet')
    expect(wrapper.find('.board-empty-meta').text()).toBe(
      'Press Pick to choose the first one.',
    )
    expect(wrapper.find('.board-stat').text()).toBe('10 remaining')
    expect(wrapper.find('.flaps').exists()).toBe(false)
    expect(wrapper.find('.board-open').exists()).toBe(false)
    expect(wrapper.find('.pick-title').text()).toBe('Pick')
  })

  it('renders flaps with per-character animation delay for a picked item', () => {
    const wrapper = mountBoard({ item: 'a b', remaining: 0, picked: 1, serial: 3 })

    const flaps = wrapper.findAll('.flap')
    expect(flaps).toHaveLength(3)
    expect(flaps[0]?.text()).toBe('a')
    expect(flaps[1]?.classes()).toContain('is-space')
    expect(flaps[2]?.text()).toBe('b')
    expect(flaps[2]?.attributes('style')).toContain('animation-delay: 28ms')
    expect(wrapper.find('h2.sr-only').text()).toBe('Picked a b')
    expect(wrapper.find('.flaps')?.attributes('title')).toBe('a b')
  })

  it('truncates long names to 48 flaps ending with the ellipsis flap', () => {
    const long = `${'x'.repeat(60)}.txt`
    const wrapper = mountBoard({ item: long, remaining: 0, picked: 1, serial: 1 })

    expect(long).toHaveLength(64)
    const flaps = wrapper.findAll('.flap')
    expect(flaps).toHaveLength(48)
    expect(flaps.at(-1)?.text()).toBe('…')
    expect(flaps.at(0)?.attributes('style')).toContain('animation-delay: 0ms')
  })

  it('caps the animation delay at 280ms after the first 20 characters', () => {
    const wrapper = mountBoard({
      item: 'y'.repeat(60),
      remaining: 0,
      picked: 1,
      serial: 2,
    })

    const flaps = wrapper.findAll('.flap')
    expect(flaps.at(20)?.attributes('style')).toContain('animation-delay: 280ms')
    expect(flaps.at(30)?.attributes('style')).toContain('animation-delay: 280ms')
  })

  it('switches the empty copy to all-picked for a fully picked folder', () => {
    const wrapper = mountBoard({ item: null, remaining: 0, picked: 4, serial: 0 })

    expect(wrapper.find('.board-empty-title').text()).toBe('All picked')
    expect(wrapper.find('.board-empty-meta').text()).toBe(
      'Clear or archive history to start over.',
    )
  })

  it('still says nothing to pick when the folder is empty', () => {
    const wrapper = mountBoard({ item: null, remaining: 0, picked: 0, serial: 0 })

    expect(wrapper.find('.board-empty-title').text()).toBe('Nothing to pick')
    expect(wrapper.find('.board-empty-meta').text()).toBe(
      'This folder is empty.',
    )
  })

  it('shows the Open control only for a picked item and emits both intents', () => {
    const picked = mountBoard({ item: 'only.txt', remaining: 0, picked: 1, serial: 1 })
    expect(picked.find('.board-open').exists()).toBe(true)

    picked.find('.pick-lever').trigger('click')
    picked.find('.board-open').trigger('click')
    expect(picked.emitted('pick')).toEqual([[]])
    expect(picked.emitted('open')).toEqual([[]])

    const empty = mountBoard()
    expect(empty.find('.board-open').exists()).toBe(false)
    empty.find('.pick-lever').trigger('click')
    expect(empty.emitted('pick')).toEqual([[]])
  })

  it('renders a disabled Undo control with the unavailable accessible name', () => {
    const wrapper = mountBoard()

    const undo = wrapper.find('.board-undo')
    expect(undo.exists()).toBe(true)
    expect(undo.text()).toBe('Undo')
    expect(undo.attributes('type')).toBe('button')
    expect(undo.attributes('aria-label')).toBe(
      'Undo last pick (nothing to undo)',
    )
    expect(undo.attributes('disabled')).toBeDefined()

    undo.trigger('click')
    expect(wrapper.emitted('undo')).toBeUndefined()
  })

  it('renders an enabled Undo control naming the item and emits undo', () => {
    const wrapper = mountBoard({
      item: 'only.txt',
      canUndo: true,
      undoLabel: 'Undo last pick: only.txt',
    })

    const undo = wrapper.find('.board-undo')
    expect(undo.text()).toBe('Undo')
    expect(undo.attributes('aria-label')).toBe('Undo last pick: only.txt')
    expect(undo.attributes('disabled')).toBeUndefined()

    undo.trigger('click')
    expect(wrapper.emitted('undo')).toEqual([[]])
  })

  it('renders a disabled Snooze after Undo and emits nothing on click', () => {
    const wrapper = mountBoard()

    const snooze = wrapper.find('.board-snooze')
    expect(snooze.exists()).toBe(true)
    expect(snooze.text()).toBe('Snooze')
    expect(snooze.attributes('type')).toBe('button')
    expect(snooze.attributes('aria-label')).toBe(
      'Snooze last pick (nothing to snooze)',
    )
    expect(snooze.attributes('disabled')).toBeDefined()

    snooze.trigger('click')
    expect(wrapper.emitted('snooze')).toBeUndefined()
  })

  it('renders an enabled Snooze naming the item and emits snooze', () => {
    const wrapper = mountBoard({
      item: 'only.txt',
      canUndo: true,
      undoLabel: 'Undo last pick: only.txt',
      canSnooze: true,
      snoozeLabel: 'Snooze last pick: only.txt',
    })

    const snooze = wrapper.find('.board-snooze')
    expect(snooze.text()).toBe('Snooze')
    expect(snooze.attributes('aria-label')).toBe(
      'Snooze last pick: only.txt',
    )
    expect(snooze.attributes('disabled')).toBeUndefined()

    snooze.trigger('click')
    expect(wrapper.emitted('snooze')).toEqual([[]])

    wrapper.find('.board-undo').trigger('click')
    expect(wrapper.emitted('undo')).toEqual([[]])
  })

  it('keeps the order Open, Undo, Snooze in the board meta row', () => {
    const wrapper = mountBoard({
      item: 'only.txt',
      canUndo: true,
      undoLabel: 'Undo last pick: only.txt',
      canSnooze: true,
      snoozeLabel: 'Snooze last pick: only.txt',
    })

    const names = wrapper
      .findAll('.board-meta button')
      .map((button) => button.classes()[0])
    expect(names).toEqual(['board-open', 'board-undo', 'board-snooze'])

    wrapper.unmount()
  })

  it('renders both controls disabled with independent names when nothing is available', () => {
    const wrapper = mountBoard({
      item: null,
      canUndo: false,
      canSnooze: false,
      undoLabel: 'Undo last pick (nothing to undo)',
      snoozeLabel: 'Snooze last pick (nothing to snooze)',
    })

    const undo = wrapper.find('.board-undo')
    const snooze = wrapper.find('.board-snooze')
    expect(undo.attributes('disabled')).toBeDefined()
    expect(snooze.attributes('disabled')).toBeDefined()
    expect(undo.attributes('aria-label')).toBe(
      'Undo last pick (nothing to undo)',
    )
    expect(snooze.attributes('aria-label')).toBe(
      'Snooze last pick (nothing to snooze)',
    )

    wrapper.unmount()
  })

  it('keeps Undo enabled for the receipt when another item is displayed', () => {
    const wrapper = mountBoard({
      item: 'beta.txt',
      canUndo: true,
      canSnooze: false,
      undoLabel: 'Undo last pick: alpha.txt',
      snoozeLabel: 'Snooze last pick: alpha.txt',
    })

    const undo = wrapper.find('.board-undo')
    const snooze = wrapper.find('.board-snooze')
    expect(undo.attributes('disabled')).toBeUndefined()
    expect(snooze.attributes('disabled')).toBeDefined()
    expect(snooze.attributes('aria-label')).toBe(
      'Snooze last pick: alpha.txt',
    )

    snooze.trigger('click')
    expect(wrapper.emitted('snooze')).toBeUndefined()

    undo.trigger('click')
    expect(wrapper.emitted('undo')).toEqual([[]])

    wrapper.unmount()
  })

  it('re-enables both controls for a new pick and keeps Undo independent', () => {
    const wrapper = mountBoard({
      item: 'gamma.txt',
      canUndo: true,
      canSnooze: true,
      undoLabel: 'Undo last pick: gamma.txt',
      snoozeLabel: 'Snooze last pick: gamma.txt',
    })

    const undo = wrapper.find('.board-undo')
    const snooze = wrapper.find('.board-snooze')
    expect(undo.attributes('disabled')).toBeUndefined()
    expect(snooze.attributes('disabled')).toBeUndefined()
    expect(undo.attributes('aria-label')).toBe('Undo last pick: gamma.txt')
    expect(snooze.attributes('aria-label')).toBe(
      'Snooze last pick: gamma.txt',
    )

    undo.trigger('click')
    expect(wrapper.emitted('undo')).toEqual([[]])
    expect(wrapper.emitted('snooze')).toBeUndefined()

    wrapper.unmount()
  })

  it('keeps Snooze a native focusable tab stop after Undo', async () => {
    const wrapper = mount(ChoiceBoard, {
      props: {
        ...defaults,
        item: 'only.txt',
        canUndo: true,
        canSnooze: false,
        undoLabel: 'Undo last pick: only.txt',
        snoozeLabel: 'Snooze last pick: only.txt',
      },
      attachTo: document.body,
    })

    const snooze = wrapper.find('.board-snooze')
    expect(snooze.element.tagName).toBe('BUTTON')
    expect(snooze.attributes('type')).toBe('button')
    expect(snooze.attributes('tabindex')).toBeUndefined()
    expect(snooze.attributes('aria-keyshortcuts')).toBeUndefined()
    expect(snooze.attributes('aria-label')).toBe(
      'Snooze last pick: only.txt',
    )
    expect(snooze.attributes('disabled')).toBeDefined()

    const buttons = wrapper.findAll('.board-meta button')
    expect(buttons.at(-2)?.classes()).toContain('board-undo')
    expect(buttons.at(-1)?.classes()).toContain('board-snooze')

    expect(wrapper.find('[aria-live]').exists()).toBe(false)
    expect(wrapper.find('[role="status"]').exists()).toBe(false)

    await wrapper.setProps({ canSnooze: true })
    const button = snooze.element as HTMLButtonElement
    button.focus()
    expect(document.activeElement).toBe(button)
    button.click()
    expect(wrapper.emitted('snooze')).toEqual([[]])

    wrapper.unmount()
  })

  it('keeps Undo a native tab stop without a shortcut binding', () => {
    const wrapper = mount(ChoiceBoard, {
      props: {
        item: 'only.txt',
        remaining: 0,
        picked: 1,
        serial: 1,
        canUndo: true,
        undoLabel: 'Undo last pick: only.txt',
        canSnooze: true,
        snoozeLabel: 'Snooze last pick: only.txt',
      },
      attachTo: document.body,
    })

    const undo = wrapper.find('.board-undo')
    expect(undo.element.tagName).toBe('BUTTON')
    expect(undo.attributes('type')).toBe('button')
    expect(undo.attributes('tabindex')).toBeUndefined()
    expect(undo.attributes('aria-keyshortcuts')).toBeUndefined()

    const button = undo.element as HTMLButtonElement
    button.focus()
    expect(document.activeElement).toBe(button)
    button.click()
    expect(wrapper.emitted('undo')).toEqual([[]])

    wrapper.unmount()
  })
})
