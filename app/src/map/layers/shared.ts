// Shared deck.gl settings for layer render functions.

/** Ground layers draw without depth testing so they don't z-fight; 3D layers still occlude them. */
export const GROUND_PARAMETERS = { depthCompare: 'always', depthWriteEnabled: false } as const

export const isSelected = (selection: { kind: string; id: string } | null, kind: string, id: string) =>
  selection?.kind === kind && selection.id === id
