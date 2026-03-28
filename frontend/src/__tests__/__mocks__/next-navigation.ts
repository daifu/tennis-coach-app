export const useRouter = jest.fn(() => ({
  push: jest.fn(),
  replace: jest.fn(),
  back: jest.fn(),
}));

export const useParams = jest.fn(() => ({ job_id: "test-job-id" }));
export const usePathname = jest.fn(() => "/");
