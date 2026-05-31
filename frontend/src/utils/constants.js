export const LAYOUT_STYLES = {
  spacious: { label: 'Spacious', description: '~2 exercises per page, large answer boxes', icon: '📐' },
  standard: { label: 'Standard', description: '~3 exercises per page, medium answer spaces', icon: '📝' },
  dense: { label: 'Dense', description: '~5 exercises per page, compact answer lines', icon: '📋' },
}

export const EXERCISE_TYPES = {
  multiple_choice: { label: 'Multiple Choice', icon: '○' },
  fill_blank: { label: 'Fill in the Blank', icon: '___' },
  show_work: { label: 'Show Your Work', icon: '✏️' },
  true_false: { label: 'True / False', icon: 'T/F' },
  matching: { label: 'Matching', icon: '↔️' },
  word_problems: { label: 'Word Problems', icon: '📖' },
}

export const ANSWER_STYLES = {
  ruled_lines: { label: 'Ruled Lines', description: 'Horizontal lines for writing' },
  dotted_lines: { label: 'Dotted Lines', description: 'Dotted lines for writing' },
  grid: { label: 'Grid Paper', description: 'Square grid for geometry/graphing' },
  plain_box: { label: 'Plain Box', description: 'Bordered box for answers' },
}

export const FONT_SIZES = {
  small: { label: 'Small (10pt)', value: 'small' },
  medium: { label: 'Medium (11pt)', value: 'medium' },
  large: { label: 'Large (12pt)', value: 'large' },
}

export const LANGUAGES = {
  english: { label: 'English', dir: 'ltr' },
  arabic: { label: 'العربية', dir: 'rtl' },
  bilingual: { label: 'Bilingual (Arabic + English)', dir: 'ltr' },
}

export const DIFFICULTY_COLORS = {
  easy: 'text-green-600 bg-green-50',
  medium: 'text-amber-600 bg-amber-50',
  hard: 'text-red-600 bg-red-50',
}
