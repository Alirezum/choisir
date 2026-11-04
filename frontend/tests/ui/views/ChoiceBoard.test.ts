import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ChoiceBoard from '../../../src/views/ChoiceBoard.vue'

const mountBoard = (
  props: {
    item: string | null
    remaining: number
    picked: number
    serial: number
  } = { item: null, remaining: 10, picked: 0, serial: 0 },
) => mount(ChoiceBoard, { props })

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
})
