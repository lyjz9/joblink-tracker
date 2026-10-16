"""Write external job data as literal Excel values, never formulas."""


def write_literal_cell(cell, value):
    cell.value = value
    if isinstance(value, str):
        cell.data_type = "s"
    return cell
