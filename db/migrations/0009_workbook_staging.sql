BEGIN;

CREATE TABLE IF NOT EXISTS staging.workbooks (
    workbook_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    import_batch_id uuid NOT NULL REFERENCES provenance.import_batches(import_batch_id) ON DELETE CASCADE,
    source_id uuid REFERENCES provenance.sources(source_id) ON DELETE RESTRICT,
    file_name text NOT NULL,
    file_checksum text NOT NULL,
    workbook_format text NOT NULL,
    sheet_count integer NOT NULL,
    inspected_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT workbooks_file_name_ck CHECK (btrim(file_name) <> ''),
    CONSTRAINT workbooks_checksum_ck CHECK (file_checksum ~ '^[0-9a-f]{64}$'),
    CONSTRAINT workbooks_format_ck CHECK (workbook_format IN ('xls','xlsx','xlsm')),
    CONSTRAINT workbooks_sheet_count_ck CHECK (sheet_count >= 0),
    UNIQUE (import_batch_id, file_checksum)
);

CREATE TABLE IF NOT EXISTS staging.workbook_sheets (
    workbook_sheet_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workbook_id uuid NOT NULL REFERENCES staging.workbooks(workbook_id) ON DELETE CASCADE,
    sheet_index integer NOT NULL,
    sheet_name text NOT NULL,
    row_count integer NOT NULL,
    column_count integer NOT NULL,
    header_row integer,
    hidden boolean NOT NULL DEFAULT false,
    CONSTRAINT workbook_sheets_index_ck CHECK (sheet_index >= 0),
    CONSTRAINT workbook_sheets_name_ck CHECK (btrim(sheet_name) <> ''),
    CONSTRAINT workbook_sheets_row_count_ck CHECK (row_count >= 0),
    CONSTRAINT workbook_sheets_column_count_ck CHECK (column_count >= 0),
    CONSTRAINT workbook_sheets_header_row_ck CHECK (header_row IS NULL OR header_row > 0),
    UNIQUE (workbook_id, sheet_index),
    UNIQUE (workbook_id, sheet_name)
);

CREATE TABLE IF NOT EXISTS staging.workbook_rows (
    workbook_row_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workbook_sheet_id uuid NOT NULL REFERENCES staging.workbook_sheets(workbook_sheet_id) ON DELETE CASCADE,
    row_number integer NOT NULL,
    row_payload jsonb NOT NULL,
    validation_status text NOT NULL DEFAULT 'unreviewed',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT workbook_rows_number_ck CHECK (row_number > 0),
    CONSTRAINT workbook_rows_status_ck CHECK (validation_status IN ('unreviewed','valid','warning','rejected')),
    UNIQUE (workbook_sheet_id, row_number)
);

CREATE TABLE IF NOT EXISTS staging.workbook_cells (
    workbook_cell_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workbook_row_id uuid NOT NULL REFERENCES staging.workbook_rows(workbook_row_id) ON DELETE CASCADE,
    column_number integer NOT NULL,
    column_letter text NOT NULL,
    cell_address text NOT NULL,
    header_name text,
    raw_value text,
    normalized_value text,
    value_type text NOT NULL,
    formula text,
    is_merged boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT workbook_cells_column_number_ck CHECK (column_number > 0),
    CONSTRAINT workbook_cells_column_letter_ck CHECK (btrim(column_letter) <> ''),
    CONSTRAINT workbook_cells_address_ck CHECK (btrim(cell_address) <> ''),
    CONSTRAINT workbook_cells_value_type_ck CHECK (value_type IN ('blank','text','number','date','datetime','boolean','formula','error','unknown')),
    UNIQUE (workbook_row_id, column_number)
);

CREATE INDEX IF NOT EXISTS workbook_rows_sheet_idx ON staging.workbook_rows(workbook_sheet_id, row_number);
CREATE INDEX IF NOT EXISTS workbook_cells_header_idx ON staging.workbook_cells(header_name);
CREATE INDEX IF NOT EXISTS workbook_cells_address_idx ON staging.workbook_cells(cell_address);

COMMENT ON TABLE staging.workbook_cells IS
    'Cell-level staging preserving workbook coordinates, raw values, normalized values, formulas, and header context before canonical mapping.';

COMMIT;
