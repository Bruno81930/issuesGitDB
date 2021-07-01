import json
import sqlite3
import GitCommits as g
import JiraIssues as j
import JavaAnalyzer as a
import pandas as pd
import os


class Connection:
    def __init__(self, conn_path, use_db=True, commit_ind=0):
        self.output_dir = os.path.realpath('./data')
        self.connection_path = os.path.join(self.output_dir, conn_path)
        self.use_db = use_db
        if self.use_db:
            self.init_db()
        self.commit_ind = commit_ind
        self.projects = []
        self.commits = []
        self.issues = []
        self.commits_files = []
        self.commit_changes = []
        self.method_data = []
        self.commits_issues_linkage = []
        self.blame = []

    def _insert(self, sql_query, data):
        if self.use_db:
            try:
                with self.connection:
                    cur = self.connection.cursor()
                    cur.execute(sql_query, data)
            except sqlite3.Error as e:
                print("Error %s:" % e.args[0])

    def init_db(self):
        self.connection = sqlite3.connect(self.connection_path)
        with open(r"table creation.sql") as f:
            cursor = self.connection.cursor()
            sql_as_string = f.read()
            cursor.executescript(sql_as_string)

    def close(self):
        pd.DataFrame(self.method_data, columns=["CommitID", "MethodName", "OldNew", "LineNumber", "Content", "Changed", "Meaning", "Tokens", "Halstead", "NewPath"]).to_csv(os.path.join(self.output_dir, r"method_data.csv"), index=False, sep='!')
        if self.use_db:
            pd.DataFrame(self.projects, columns=["ProjectName", "JiraProjectId", "GitRepositoryPath"]).to_csv(os.path.join(self.output_dir, f"projects_{self.commit_ind}.csv"), index=False, sep='!')
            pd.DataFrame(self.commits, columns=["CommitID", "ProjectName", "Summary", "Message", "Date", "ParentID"]).to_csv(os.path.join(self.output_dir, f"commits_{self.commit_ind}.csv"), index=False, sep='!')
            pd.DataFrame(self.issues, columns=["IssueID", "IssueType", "ProjectName", "Summary", "Description", "Status", "Date"]).to_csv(os.path.join(self.output_dir, f"issues_{self.commit_ind}.csv"), index=False, sep='!')
            pd.DataFrame(self.commits_files, columns=["CommitID", "Path", "FileType"]).to_csv(os.path.join(self.output_dir, f"commits_files_{self.commit_ind}.csv"), index=False, sep='!')
            pd.DataFrame(self.commit_changes, columns=["CommitID", "MethodName", "NewPath", "OldPath"]).to_csv(os.path.join(self.output_dir, f"commit_changes_{self.commit_ind}.csv"), index=False, sep='!')
            pd.DataFrame(self.commits_issues_linkage, columns=["IssueID", "CommitID"]).to_csv(os.path.join(self.output_dir, f"commits_issues_linkage_{self.commit_ind}.csv"), index=False, sep='!')
            self.connection.close()

    def insert_project(self, projectName, JiraProjectId):
        self._insert("INSERT INTO Projects (ProjectName, JiraProjectId, GitRepositoryPath) VALUES (?,?,?)", (projectName, JiraProjectId, ""))
        self.projects.append((projectName, JiraProjectId, ""))

    def insert_commit(self, commit, projectName):
        self._insert("INSERT INTO Commits (CommitID, ProjectName, Summary, Message, Date, ParentID) VALUES (?,?,?,?,?,?)", (commit.id, projectName, commit.summary, commit.message, commit.date, commit.parent_id))
        self.commits.append((commit.id, projectName, commit.summary, commit.message, commit.date, commit.parent_id))
        blame = commit.blame()
        for f in blame:
            for ind, commit_id, source_line in blame[f]:
                self.blame.append((commit.id, projectName, f, ind, commit_id.hexsha, source_line))
                self._insert(
                    "INSERT INTO Blame (CommitID, ProjectName, FilePath, LineNumber, CreatorCommit, SourceLine) VALUES (?,?,?,?,?,?)",
                    (commit.id, projectName, f, ind, commit_id.hexsha, source_line))

    def insert_issue(self, issue, projectName):
        issue_id = j.get_issue_id(issue)
        issue_type = j.get_issue_type(issue)
        summary = j.get_issue_summary(issue)
        desc = j.get_issue_description(issue)
        status = j.get_issue_status(issue)
        time = j.get_issue_creation_date(issue)
        self._insert("INSERT INTO JiraIssues (IssueID, IssueType, ProjectName, Summary, Description, Status, Date) VALUES (?,?,?,?,?,?,?)", (issue_id, issue_type, projectName, summary, desc, status, time))
        self.issues.append((issue_id, issue_type, projectName, summary, desc, status, time))

    def insert_file(self, commit, file_path, file_type):
        self._insert("INSERT INTO CommitFiles (CommitID, Path, FileType) VALUES (?,?,?)", (commit.id, file_path, file_type))
        self.commits_files.append((commit.id, file_path, file_type))

    def insert_changes(self, commit, diff):
        method_name, new_path, new_lines, old_path, old_lines = diff
        self._insert("INSERT INTO CommitChanges (CommitID, MethodName, NewPath, OldPath) VALUES (?,?,?,?)", (commit.id, method_name, new_path, old_path))
        self.commit_changes.append((commit.id, method_name, new_path, old_path))

    def insert_line(self, commit, method_name, line, new_path):
        line_type = line.line_type
        line_number = line.line_number
        content = line.content
        changed = line.is_changed
        if line.meaning == '{}':
            meaning = ""
        else:
            meaning = json.dumps(line.meaning)
        if line.tokens == '{}':
            token = ""
        else:
            token = json.dumps(line.tokens)
        if line.halstead == '{}':
            halstead = ""
        else:
            halstead = json.dumps(line.halstead)
        self._insert("INSERT INTO MethodData (CommitID, MethodName, OldNew, LineNumber, Content, Changed, Meaning, Tokens, Halstead, NewPath) VALUES (?,?,?,?,?,?,?, ?, ?, ?)",
                     (commit.id, method_name, line_type, line_number, content, changed, meaning, token, halstead, new_path))
        self.method_data.append((commit.id, method_name, line_type, line_number, content, changed, meaning, token, halstead, new_path))

    def insert_linkage(self, commit, issue):
        issue_id = j.get_issue_id(issue)
        self._insert("INSERT INTO CommitsIssuesLinkage (IssueID, CommitID) VALUES (?,?)", (issue_id, commit.id))
        self.commits_issues_linkage.append((issue_id, commit.id))


def get_connection(path, use_db):
    return Connection(path, use_db)


def close_connection(conn):
    conn.close()


def insert_commit(conn, commit, projectName, quick_mode=True):
    if not quick_mode:
        conn.insert_commit(commit, projectName)

        for code_file in commit.code_files:
            conn.insert_file(commit, code_file[1], "CODE")
        for test_file in commit.test_files:
            conn.insert_file(commit, test_file[1], "TEST")

    changes = g.get_commit_changes(commit)
    if changes is not None:
        for diff in changes:
            insert_changes(conn, commit, diff, quick_mode)


def insert_changes(conn, commit, diff, quick_mode):
    if not quick_mode:
        conn.insert_changes(commit, diff)
    method_name, new_path, new_lines, old_path, old_lines = diff
    changed_lines = a.analyze_changes(old_lines, new_lines)
    for line in changed_lines:
        conn.insert_line(commit, method_name, line, new_path)
