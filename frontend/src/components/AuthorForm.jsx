import { useState } from 'react'

const HINTS = {
  fio: 'Формат: Иванов Иван Иванович\n(кириллица, три слова)',
  address: 'Формат: 000000, Москва, ул. Примерная, д. 1',
  phone: 'Формат: +7xxxxxxxxxx\nПример: +79161234567',
  email: 'Формат: name@email.ru',
  inn: 'ИНН — ровно 12 цифр',
  passport: 'Формат: 0000 000000 ГУ МВД по Московской области 01.01.2000',
  snils: 'СНИЛС — ровно 11 цифр',
  birthday: 'Формат: ДД.ММ.ГГГГ\nПример: 01.01.1990',
  skill: 'Кратко опишите творческий вклад автора',
}

const PATTERNS = {
  fio: /^[А-ЯЁа-яё]+ [А-ЯЁа-яё]+ [А-ЯЁа-яё]+$/,
  address: /^\d{6},\s*.+$/,
  phone: /^\+7\d{10}$/,
  email: /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/,
  inn: /^\d{12}$/,
  passport: /^\d{4}\s\d{6}\s.+\s\d{2}\.\d{2}\.\d{4}$/,
  snils: /^\d{11}$/,
  // Note: regex validates format only; calendar correctness (e.g. Feb 31) is not checked.
  birthday: /^(0[1-9]|[12]\d|3[01])\.(0[1-9]|1[0-2])\.(19|20)\d{2}$/,
}

function InputWithTooltip({ label, name, value, onChange, required }) {
  const [focused, setFocused] = useState(false)

  const hint = HINTS[name]
  const pattern = PATTERNS[name]
  const touched = value.length > 0
  const valid = !pattern || pattern.test(value)
  const showError = touched && !valid
  const errorMsg = showError ? getErrorMsg(name) : ''

  return (
    <div className="field tooltip-container">
      <label htmlFor={name}>{label}{required && ' *'}</label>
      <input
        id={name}
        type="text"
        value={value}
        autoComplete="off"
        className={showError ? 'error' : ''}
        onChange={(e) => onChange(name, e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      />
      {focused && hint && <div className="tooltip">{hint}</div>}
      <div className="field-error">{errorMsg}</div>
    </div>
  )
}

function getErrorMsg(name) {
  const msgs = {
    fio: 'Иванов Иван Иванович — кириллица, три слова',
    address: 'Начните с 6-значного индекса: 000000, ...',
    phone: '+7 и 10 цифр, например +79161234567',
    email: 'Корректный email, например user@mail.ru',
    inn: 'Ровно 12 цифр',
    passport: '0000 000000 Орган ДД.ММ.ГГГГ',
    snils: 'Ровно 11 цифр',
    birthday: 'ДД.ММ.ГГГГ, например 01.01.1990',
  }
  return msgs[name] || 'Неверный формат'
}

export function isAuthorValid(author) {
  return Object.keys(PATTERNS).every((key) => {
    const val = author[key] || ''
    return PATTERNS[key].test(val)
  })
}

const EMPTY_AUTHOR = {
  fio: '', address: '', phone: '', email: '',
  inn: '', passport: '', snils: '', birthday: '', skill: '',
}

export function AuthorForm({ index, author, onChange, onRemove, canRemove }) {
  const handleChange = (field, val) => onChange(index, field, val)

  return (
    <div className="card">
      <div className="author-header">
        <h3>Автор {index + 1}</h3>
        {canRemove && (
          <button className="btn-danger" onClick={() => onRemove(index)}>
            Удалить
          </button>
        )}
      </div>
      <div className="field-grid">
        <InputWithTooltip label="ФИО"        name="fio"      value={author.fio}      onChange={handleChange} required />
        <InputWithTooltip label="Адрес"      name="address"  value={author.address}  onChange={handleChange} required />
        <InputWithTooltip label="Телефон"    name="phone"    value={author.phone}    onChange={handleChange} required />
        <InputWithTooltip label="Email"      name="email"    value={author.email}    onChange={handleChange} required />
        <InputWithTooltip label="ИНН"        name="inn"      value={author.inn}      onChange={handleChange} required />
        <InputWithTooltip label="СНИЛС"      name="snils"    value={author.snils}    onChange={handleChange} required />
        <InputWithTooltip label="Дата рождения" name="birthday" value={author.birthday} onChange={handleChange} required />
        <div className="field-full">
          <InputWithTooltip label="Паспорт" name="passport" value={author.passport} onChange={handleChange} required />
        </div>
        <div className="field-full">
          <InputWithTooltip label="Творческий вклад" name="skill" value={author.skill} onChange={handleChange} />
        </div>
      </div>
    </div>
  )
}

export { EMPTY_AUTHOR }
