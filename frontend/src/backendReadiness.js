export async function probeSession(getUser) {
  try { return { ready: true, user: await getUser() } }
  catch (error) { return { ready: error.status === 401, user: null } }
}
