import MatrixDB as db
import GitCommits as g
import JiraIssues as j
import Matrix
import sys

if __name__ == '__main__':
    # Set variables according to the project

    PROJECT_NAME = sys.argv[1] # "commons-math"
    JIRA_PROJECT_ID = sys.argv[2] # "MATH"
    commits_start = None
    commits_end = None
    USE_DB = False
    QUICK_MODE = False
    if len(sys.argv) > 3:
        window_size = 10
        commits_start = int(sys.argv[1]) * window_size
        commits_end = commits_start + window_size
        PROJECT_NAME = sys.argv[2]  # "commons-math"
        JIRA_PROJECT_ID = sys.argv[3]  # "MATH"
        if len(sys.argv) > 4:
            QUICK_MODE = True

    DB_PATH = f"CommitIssueDB_{commits_start}.db"
    GIT_REPO_PATH_LOCAL = r"local_repo"
    JIRA_PATH = r"http://issues.apache.org/jira"

    # Get DB connection
    db_connection = db.get_connection(DB_PATH, USE_DB)

    # Project Handling
    db_connection.insert_project(PROJECT_NAME, JIRA_PROJECT_ID)

    # Commits Handling
    g.set_repo_path(GIT_REPO_PATH_LOCAL)
    comms = g.get_commits_files(GIT_REPO_PATH_LOCAL)
    all_commits = list(filter(lambda c: c.is_java, comms))
    commits = all_commits
    if commits_start is not None:
        commits = all_commits[commits_start: commits_end]
        if len(commits) == 0:
            exit()

    for ind, commit in enumerate(commits):
        db.insert_commit(db_connection, commit, PROJECT_NAME, QUICK_MODE)

    if not QUICK_MODE or commits_start == 0:
        # Issues Handling
        j.set_jira(JIRA_PATH)
        jql_features = 'project = {0} AND issuetype = "New Feature" AND statusCategory = Done'.format(JIRA_PROJECT_ID)
        jql_bugs_improvements = 'project = {0} AND issuetype in (Bug, Improvement) AND statusCategory = Done'.format(
            JIRA_PROJECT_ID)

        issues_features = j.get_issues_list(jql_features)
        for issue in issues_features:
            db_connection.insert_issue(issue, PROJECT_NAME)

        issues_bugs_improvements = j.get_issues_list(jql_bugs_improvements)
        for issue in issues_bugs_improvements:
            db_connection.insert_issue(issue, PROJECT_NAME)

        all_issues = issues_bugs_improvements + issues_features  # union both issue lists to one
        # Matrix Handling
        m = Matrix.create_matrix(all_issues, all_commits)
        for issue, commit in m:
            db_connection.insert_linkage(commit, issue)

    # DONE
    db.close_connection(db_connection)
