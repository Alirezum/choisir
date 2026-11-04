import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import OptionsPanel from '../../../src/views/OptionsPanel.vue'

const mountPanel = (
  props: {
    log: string
    seed: string
    dry: boolean
    hidden: boolean
    mode: 'all' | 'files' | 'dirs'
  } = { log: '', seed: '', dry: false, hidden: false, mode: 'all' },
) => mount(OptionsPanel, { props })

describe('OptionsPanel', () => {
  it('renders the header, labels, and placeholders', () => {
    const wrapper = mountPanel()

    expect(wrapper.find('.panel-header').text()).toBe(
      'Changes apply to the next pick.',
    )
    expect(wrapper.find('legend').text()).toBe('Mode')
    expect(
      Array.from(wrapper.findAll('label.field > span')).map((el) => el.text()),
    ).toEqual(['Log file', 'Seed'])
    expect(wrapper.find('input[placeholder]').attributes('placeholder')).toBe(
      'empty = <directory>/.choosier.jsonl',
    )
    expect(wrapper.findAll('input').at(1)?.attributes('placeholder')).toBe(
      'empty = random',
    )
  })

  it('binds the log and seed inputs to their models', async () => {
    const wrapper = mountPanel()
    const [logInput, seedInput] = wrapper.findAll('input')

    ;(logInput.element as HTMLInputElement).value = '/tmp/log.jsonl'
    await logInput.trigger('input')
    ;(seedInput.element as HTMLInputElement).value = '42'
    await seedInput.trigger('input')

    expect(wrapper.emitted('update:log')).toEqual([['/tmp/log.jsonl']])
    expect(wrapper.emitted('update:seed')).toEqual([['42']])
  })

  it('binds the checkboxes and updates them', async () => {
    const wrapper = mountPanel()
    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    expect(checkboxes).toHaveLength(2)

    await checkboxes[0]?.setValue(true)
    await checkboxes[1]?.setValue(true)

    expect(wrapper.emitted('update:dry')).toEqual([[true]])
    expect(wrapper.emitted('update:hidden')).toEqual([[true]])
    expect(checkboxes[0]?.attributes('id')).toBeUndefined()
  })

  it('renders the mode radios with all three mutually exclusive choices', () => {
    const wrapper = mountPanel()
    const radios = wrapper.findAll('input[type="radio"]')

    expect(radios).toHaveLength(3)
    expect(radios.map((radio) => radio.attributes('value'))).toEqual([
      'all',
      'files',
      'dirs',
    ])
    expect(radios[0]?.element.checked).toBe(true)
  })

  it('emits a mode change when a radio is selected', async () => {
    const wrapper = mountPanel()
    const radios = wrapper.findAll('input[type="radio"]')

    await radios[1]?.setValue()

    expect(wrapper.emitted('update:mode')).toEqual([['files']])
  })
})
