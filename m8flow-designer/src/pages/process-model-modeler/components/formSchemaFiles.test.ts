import { describe, expect, it } from 'vitest';

import {
  formSchemaBaseFromLabel,
  formSchemaFileNames,
  isValidFormSchemaBase,
  schemaBaseName,
} from './formSchemaFiles';

describe('isValidFormSchemaBase', () => {
  it('accepts lowercase hyphenated names of at least three characters', () => {
    expect(isValidFormSchemaBase('abc')).toBe(true);
    expect(isValidFormSchemaBase('sample-form')).toBe(true);
    expect(isValidFormSchemaBase('wfh-form')).toBe(true);
  });

  it('rejects empty, short, or illegal identifiers', () => {
    expect(isValidFormSchemaBase('')).toBe(false);
    expect(isValidFormSchemaBase('ab')).toBe(false);
    expect(isValidFormSchemaBase('Sample Form')).toBe(false);
    expect(isValidFormSchemaBase('sample_form')).toBe(false);
    expect(isValidFormSchemaBase('-sample')).toBe(false);
  });
});

describe('schemaBaseName', () => {
  it('strips the schema / ui / example suffixes', () => {
    expect(schemaBaseName('sample-form-schema.json')).toBe('sample-form');
    expect(schemaBaseName('sample-form-uischema.json')).toBe('sample-form');
    expect(schemaBaseName('sample-form-exampledata.json')).toBe('sample-form');
    expect(schemaBaseName('wfh-form.schema.json')).toBe('wfh-form');
  });
});

describe('formSchemaBaseFromLabel', () => {
  it('slugifies a task name or element id into a valid base', () => {
    expect(formSchemaBaseFromLabel('Task')).toBe('task');
    expect(formSchemaBaseFromLabel('Example user task')).toBe('example-user-task');
    expect(formSchemaBaseFromLabel('Activity_1abc')).toBe('activity-1abc');
  });

  it('pads short labels and falls back to form', () => {
    expect(formSchemaBaseFromLabel('ab')).toBe('ab-form');
    expect(formSchemaBaseFromLabel('!!!')).toBe('form');
  });
});

describe('formSchemaFileNames', () => {
  it('builds the three companion filenames from a base', () => {
    expect(formSchemaFileNames('sample-form')).toEqual({
      schema: 'sample-form-schema.json',
      ui: 'sample-form-uischema.json',
      example: 'sample-form-exampledata.json',
    });
  });
});
