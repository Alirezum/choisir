import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'

import { api } from '../api.ts'
import type { PreviewImage, PreviewModel } from '../types.ts'
import type { ViewableImage } from '../view-models.ts'

export interface PreviewDeps {
  path: () => string
  preview: () => PreviewModel | null
}

export interface PreviewBinding {
  viewerIndex: Ref<number | null>
  videoError: Ref<boolean>
  images: ComputedRef<ViewableImage[]>
  showNumbers: ComputedRef<boolean>
  imageLabel: ComputedRef<string>
  metaLine: ComputedRef<string>
  bodyText: ComputedRef<string>
  videoUrl: ComputedRef<string>
  frameLabel: (image: PreviewImage, index: number) => string
  openViewer: (index: number) => void
  closeViewer: () => void
  reportVideoError: () => void
  reset: () => void
}

const MEDIA_LABELS: Record<string, string> = {
  'video/mp4': 'MP4',
  'video/webm': 'WEBM',
  'video/quicktime': 'MOV',
  'video/x-matroska': 'MKV',
  'video/ogg': 'OGV',
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function mediaLabel(mediaType: string): string {
  return (
    MEDIA_LABELS[mediaType] ??
    (mediaType.split('/')[1] ?? mediaType).toUpperCase()
  )
}

/**
 * View-local unit for the preview column: ready-to-render labels, meta/body
 * copy, grid and viewer media addresses, and the viewer/video transient state.
 * It builds client media addresses only; it never performs a request.
 */
export function usePreview(deps: PreviewDeps): PreviewBinding {
  const viewerIndex = ref<number | null>(null)
  const videoError = ref(false)

  function imageVariant(total: number): 'thumb' | 'preview' {
    return total === 1 ? 'preview' : 'thumb'
  }

  const images = computed<ViewableImage[]>(() => {
    const list = deps.preview()?.images ?? []
    const path = deps.path()
    return list.map((image) => ({
      ...image,
      src: api.imageUrl(path, image.index, imageVariant(list.length)),
      fullSrc: api.imageUrl(path, image.index),
    }))
  })

  const showNumbers = computed(() =>
    images.value.some((image) => image.index !== null),
  )

  const imageLabel = computed(() => {
    if (images.value.length === 0) return ''
    const total = deps.preview()?.image_total ?? images.value.length
    if (total > images.value.length) {
      return `${images.value.length} of ${total} images`
    }
    return total === 1 ? '1 image' : `${total} images`
  })

  const metaLine = computed(() => {
    const preview = deps.preview()
    if (preview === null) return ''
    if (preview.kind === 'image' && preview.images[0] !== undefined) {
      const image = preview.images[0]
      return `${mediaLabel(image.media_type)}, ${formatSize(image.size)}`
    }
    if (preview.kind === 'archive' && preview.images.length > 0) {
      return 'Archive'
    }
    if (preview.kind === 'video' && preview.video !== null) {
      return `${mediaLabel(preview.video.media_type)}, ${formatSize(preview.video.size)}`
    }
    return ''
  })

  const bodyText = computed(() => {
    const preview = deps.preview()
    if (preview === null || metaLine.value !== '') return ''
    return preview.text
  })

  const videoUrl = computed(() =>
    deps.path() === '' ? '' : api.videoUrl(deps.path()),
  )

  function frameLabel(image: PreviewImage, index: number): string {
    return String((image.index ?? index) + 1).padStart(2, '0')
  }

  function reset(): void {
    viewerIndex.value = null
    videoError.value = false
  }

  function openViewer(index: number): void {
    viewerIndex.value = index
  }

  function closeViewer(): void {
    viewerIndex.value = null
  }

  function reportVideoError(): void {
    videoError.value = true
  }

  watch(deps.preview, reset)

  return {
    viewerIndex,
    videoError,
    images,
    showNumbers,
    imageLabel,
    metaLine,
    bodyText,
    videoUrl,
    frameLabel,
    openViewer,
    closeViewer,
    reportVideoError,
    reset,
  }
}
