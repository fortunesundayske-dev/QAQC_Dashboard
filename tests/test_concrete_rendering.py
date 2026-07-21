import unittest

import pandas as pd

from database import concrete_records


class ConcreteRenderingTests(unittest.TestCase):
    def test_project_options_reuse_loaded_data_without_duplicates(self):
        frames = {
            "Project Register": pd.DataFrame(
                {"Project": ["IA Warehouse", "Bonny Road Expansion Project"]}
            ),
            "Concrete Tracker": pd.DataFrame(
                {"Project": ["  ia warehouse  ", "New Project", "NEW  PROJECT"]}
            ),
        }

        projects = concrete_records.list_concrete_projects_from_data(frames)

        self.assertEqual(
            projects,
            ["Bonny Road Expansion Project", "IA Warehouse", "New Project"],
        )


if __name__ == "__main__":
    unittest.main()
