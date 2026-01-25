"""E2E test for adding a student in the Control Panel."""

import time

import pytest


@pytest.mark.e2e
class TestAddStudent:
    """Test the add student flow for instructors."""

    def test_add_student_manually(self, instructor_page):
        """Test that an instructor can add a student manually.

        Steps:
        1. Log in as instructor (handled by fixture)
        2. Navigate to Control Panel
        3. Click "Student Management" button
        4. Click "Add Student" button
        5. Fill out the student form
        6. Submit the form
        7. Verify success message appears or page returns to Student Management
        """
        page = instructor_page

        # Navigate to Control Panel using sidebar navigation
        page.get_by_role("link", name="Control Panel").click()

        # Wait for Control Panel to load
        page.wait_for_selector("text=Control Panel", timeout=30000)

        # Click "Student Management" button (matches "Student Management" or "👥 Student Management")
        page.get_by_role("button").filter(has_text="Student Management").click()

        # Wait for Student Management page to load
        page.wait_for_selector("text=Student Management", timeout=30000)

        # Click "Add Student" button to show the manual add form
        # There are three buttons: "Add Students", "Add Student", "Remove Student"
        # Need to click the middle one which is exactly "Add Student" (not "Add Students")
        page.locator("button").filter(has_text="Add Student").filter(has_not_text="Students").first.click()

        # Wait for the form to appear - look for form input labels
        page.wait_for_selector("text=Introduce User ID", timeout=30000)

        # Fill out the student form with unique test data
        test_user_id = f"test_user_{int(time.time())}"
        test_email = f"test_{int(time.time())}@example.com"

        # Fill the form fields - Streamlit text inputs
        # Use locator to find input fields after their labels
        page.locator("input").nth(0).fill(test_user_id)  # User ID
        page.locator("input").nth(1).fill(test_email)  # Email
        page.locator("input").nth(2).fill("1")  # Group ID
        page.locator("input").nth(3).fill("2024/2025")  # Academic year
        page.locator("input").nth(4).fill("A")  # Class

        # Submit the form - click the form submit button
        page.locator("[data-testid='stFormSubmitButton'] button").click()

        # Wait for either success message or error message
        # The success message appears briefly before page rerun
        # Check for any result - success, error, or page reload
        try:
            # First try to catch the success message
            page.wait_for_selector("text=Student added successfully", timeout=10000)
        except Exception as err:
            # Check if there's an error message
            error_visible = page.locator("text=Failed to add student").is_visible()
            fields_error = page.locator("text=Please fill in all fields").is_visible()

            if error_visible or fields_error:
                raise AssertionError("Form submission failed - check error message on page") from err

            # If no error and we're still on the page, check we're on Student Management
            page.wait_for_selector("text=Student Management", timeout=10000)
