use std::{
    ffi::{OsStr, OsString},
    path::{Path, PathBuf},
    process::{Command, ExitStatus, Stdio},
};

use crate::error::CliError;

#[derive(Debug, Clone)]
pub struct CommandSpec {
    program: OsString,
    args: Vec<OsString>,
    cwd: PathBuf,
    env: Vec<(OsString, OsString)>,
    remove_env: Vec<OsString>,
}

#[derive(Debug)]
pub struct Captured {
    pub status: ExitStatus,
    pub stdout: String,
    pub stderr: String,
}

impl CommandSpec {
    pub fn new(program: impl Into<OsString>, cwd: impl Into<PathBuf>) -> Self {
        Self {
            program: program.into(),
            args: Vec::new(),
            cwd: cwd.into(),
            env: Vec::new(),
            remove_env: Vec::new(),
        }
    }

    pub fn arg(mut self, arg: impl Into<OsString>) -> Self {
        self.args.push(arg.into());
        self
    }

    pub fn args<I, S>(mut self, args: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: Into<OsString>,
    {
        self.args.extend(args.into_iter().map(Into::into));
        self
    }

    pub fn env(mut self, key: impl Into<OsString>, value: impl Into<OsString>) -> Self {
        self.env.push((key.into(), value.into()));
        self
    }

    pub fn env_remove(mut self, key: impl Into<OsString>) -> Self {
        self.remove_env.push(key.into());
        self
    }

    pub fn run(&self) -> Result<(), CliError> {
        let rendered = self.render();
        println!("+ {rendered}");
        let status = self
            .command()
            .stdin(Stdio::inherit())
            .stdout(Stdio::inherit())
            .stderr(Stdio::inherit())
            .status()
            .map_err(|source| CliError::CommandStart {
                command: rendered.clone(),
                source,
            })?;
        if status.success() {
            Ok(())
        } else {
            Err(CliError::CommandFailed {
                command: rendered,
                status,
            })
        }
    }

    pub fn capture(&self) -> Result<Captured, CliError> {
        let rendered = self.render();
        println!("+ {rendered}");
        let output = self
            .command()
            .stdin(Stdio::null())
            .output()
            .map_err(|source| CliError::CommandStart {
                command: rendered.clone(),
                source,
            })?;
        let stdout = String::from_utf8(output.stdout).map_err(|_| CliError::NonUtf8Output {
            command: rendered.clone(),
        })?;
        let stderr = String::from_utf8(output.stderr).map_err(|_| CliError::NonUtf8Output {
            command: rendered.clone(),
        })?;
        print!("{stdout}");
        eprint!("{stderr}");
        Ok(Captured {
            status: output.status,
            stdout,
            stderr,
        })
    }

    pub fn capture_success(&self) -> Result<Captured, CliError> {
        let captured = self.capture()?;
        if captured.status.success() {
            Ok(captured)
        } else {
            Err(CliError::CommandFailed {
                command: self.render(),
                status: captured.status,
            })
        }
    }

    pub fn require_failure(&self) -> Result<Captured, CliError> {
        let captured = self.capture()?;
        if captured.status.success() {
            Err(CliError::ExpectedFailureAccepted {
                command: self.render(),
            })
        } else {
            Ok(captured)
        }
    }

    pub fn render(&self) -> String {
        let mut parts = Vec::with_capacity(self.args.len() + 1);
        parts.push(render_os(&self.program));
        parts.extend(self.args.iter().map(|arg| render_os(arg)));
        format!("(cd {} && {})", self.cwd.display(), parts.join(" "))
    }

    fn command(&self) -> Command {
        let mut command = Command::new(&self.program);
        command.args(&self.args).current_dir(&self.cwd);
        for (key, value) in &self.env {
            command.env(key, value);
        }
        for key in &self.remove_env {
            command.env_remove(key);
        }
        command
    }
}

fn render_os(value: &OsStr) -> String {
    let value = value.to_string_lossy();
    if value
        .chars()
        .all(|character| character.is_ascii_alphanumeric() || "-._/:+=@".contains(character))
    {
        value.into_owned()
    } else {
        format!("{:?}", value.as_ref())
    }
}

pub fn require_path(path: &Path) -> Result<(), CliError> {
    if path.exists() {
        Ok(())
    } else {
        Err(CliError::MissingPath(path.to_path_buf()))
    }
}
